import blpapi
from collections import defaultdict
from pandas import DataFrame
from datetime import datetime, date
import pandas as pd
import testAccess
import xlwings as xw
import numpy as np
 
 
def bdh(ticker_list, fld_list, start_date, end_date=date.today().strftime('%Y%m%d'), periodselection='DAILY'):
        """
        Get ticker_list and field_list
        return dictionary of pandas dataframe with ticker as keyname
        """
        host='localhost'
        port=8194 # Create and fill the request for the historical data
        sessionOptions = blpapi.SessionOptions() # Create SessionOption Object
        sessionOptions.setServerHost(host)  # Set Session Option host
        sessionOptions.setServerPort(port)  # Set Session Option port, default as 8194
        session = blpapi.Session(sessionOptions) # Create Session Object
        if not session.start():  
            print("Failed to start session.")
        
        if not session.openService("//blp/refdata"):  
            print("Failed to open //blp/refdata")
        
        refDataService = session.getService("//blp/refdata")  # get refdata service for historical data
        if isinstance(ticker_list,str): # change a single string to list
            ticker_list = [ticker_list]
        if isinstance(fld_list,str):  # change a single string to list
            fld_list = [fld_list]
        if hasattr(start_date, 'strftime'): # convert to datetime format
            start_date = start_date.strftime('%Y%m%d')
            print start_date
        if hasattr(end_date, 'strftime'): # convert to datetime format
            end_date = end_date.strftime('%Y%m%d')
            print end_date
        #print ticker_list,fld_list,start_date, end_date
        request = refDataService.createRequest("HistoricalDataRequest")  # Create request
        for t in ticker_list:
            request.getElement("securities").appendValue(t)  # Set Request Securites element
        for f in fld_list:
            request.getElement("fields").appendValue(f)  # Set Request Fields element
        request.set("periodicityAdjustment", "CALENDAR") # Set as the last business day of period required
        request.set("periodicitySelection", periodselection) # Set Period e.g WEEKLY
        request.set("startDate", start_date) # Set Request Start Date
        request.set("endDate", end_date) # Set Request End Date

        #print("Sending Request:", request)
        session.sendRequest(request)  # Send the request
        data = defaultdict(dict)  # defaultdict - later convert to pandas
        # Process received events
        while (True):
            ev = session.nextEvent() 
            if ev.eventType() in [5,6]: # filter events that contain historical data
                for msg in ev:
                   #print msg
                   ticker = msg.getElement('securityData').getElement('security').getValue()  # get security ticker from event
                   fieldData = msg.getElement("securityData").getElement("fieldData") 
                   # Fill default dictionary
                   for i in range(fieldData.numValues()):  
                        for j in range(1, fieldData.getValue(i).numElements()):
                            data[(ticker, fld_list[j - 1])][
                                    fieldData.getValue(i).getElement(0).getValue()] = fieldData.getValue(i).getElement(j).getValue()
            if ev.eventType() == blpapi.Event.RESPONSE: # Response completly received, so we could exit
                break
        
        pd_dict=dict() # Create empty dictionary 
        
        if len(data) == 0: # In case of security error case
            return DataFrame()
        
        Default_Dict_Keys=data.keys() #  get keys of default dictionary
        check=[0]*len(ticker_list) #  Purpose: check whether the a ticker has a dataframe or not 
        
        for i in range(len(ticker_list)):
            for each in Default_Dict_Keys:
                # ticker doesn't have a dataframe yet, create dataframe with field and date as index 
                if each[0]==ticker_list[i] and check[i]==0:  
                    pd_dict[ticker_list[i]]=DataFrame(zip(data[each].values(),data[each].keys()),columns=[each[1],'Date'])
                    pd_dict[ticker_list[i]].set_index('Date',inplace=True)
                    check[i]=1
                # ticker has a dataframe, add new field to existing dataframe
                if each[0]==ticker_list[i] and check[i]==1:
                   pd_dict[ticker_list[i]].loc[:,each[1]]=pd.Series(data[each].values(),index=pd_dict[ticker_list[i]].index)
            # sort dataframe based on column names and index
            pd_dict[ticker_list[i]].sort_index(inplace=True)
            pd_dict[ticker_list[i]].sort_index(axis=1, inplace=True)
        return pd_dict
    


def pd2DB (data,crsr):
    """Write DataFrame to  Database from dataframe dictionary
    Argument:
    data --dataframe dictionary
    crsr --cursor from database connection
    """
    # extract all table names from database
    tbls = crsr.tables(tableType='TABLE').fetchall()
    tbls_names=[]
    for tbl in tbls:
        tbls_names.append(str(tbl.table_name))
    #write each df to database
    for key, df in data.items():
        key = ''.join(key.split()) # del all spaces in key
        # if table not created, create a new table
        if key not in tbls_names: 
            header=list(df) # get column names of dataframe
            Index=df.index.name # get index name
            # create SQL query for create new table
            cols=" (["+Index+"] date"
            for each in header:
                cols=cols+", ["+each+"]"+" double"
            cols=cols+", PRIMARY KEY([Date]))"
            query_ct="CREATE TABLE "+ str(key)+cols
            crsr.execute(query_ct)
            # Insert each row in DataFrame to Database
            for index, row in df.iterrows():
                row=list(row)
                row.insert(0,index)
                var_string = ', '.join('?' * len(row))
                query_insert="INSERT INTO "+str(key)+" VALUES (%s);" % var_string
                crsr.execute(query_insert,row)
        # write new data to database if a table already exists
        else: 
            # Find last index in the database
            query_last="select top 1 [Date] from "+str(key)+" order by [Date] desc"
            crsr.execute(query_last)  
            Last_Index = datetime.date(crsr.fetchone()[0])
            # Find first Index in dataframe
            df_first_index=df.index.tolist()[0]
            if df_first_index <Last_Index: 
                df=df.loc[Last_Index :]   # create a dataframe piece
                if len(df.index)>1:
                    count=0
                    for index, row in df.iterrows():
                        if count==0:  # skip the first row
                            count=1
                        else:  # write to the database starting from the second row of df piece
                            row=list(row)
                            row.insert(0,index)
                            var_string = ', '.join('?' * len(row))
                            query_insert="INSERT INTO "+str(key)+" VALUES (%s);" % var_string
                            crsr.execute(query_insert,row)
            else: print "Extract Dates Range is not enough!"
   

def DF_Merge(key,value,heads,flds,start,end):
    """Merge seperate DataFrames into one TimeSeries df dict
    Argument
    key -- dictionary key
    value -- list of tickers
    flds -- list of fields
    start --start date e.g "20070101"
    end --end date e.g "20070101"
    heads -- desired col sequence in list format
    Output
    Dictionary of DataFrame
    """    
    #print key,value,heads,flds,start,end
    data=bdh(value,flds,start,end,periodselection='WEEKLY')
    count=0 
    headers=dict(zip(value,heads))
    for key, each in data.items():
        each.rename(columns={flds[0]:headers[key]},inplace=True)
        #print each.head()
        if count==0:
            result=each
            count=count+1
        else:
            result=pd.merge(result,each, left_index=True, right_index=True)
    result=result[heads] # re-arrange column sequence has heads
    #print result.head()
    return result


def removeUni(l):
    """convert unicode to string"""
    result=[]
    for each in l:
        each=each.replace(u'\xa0', ' ').encode('utf-8')
        result.append(each)
    return result


@xw.func
@xw.arg('spot', np.array, ndim=2)
@xw.arg('fwd', np.array, ndim=2)
@xw.arg('startD', np.array, ndim=2)
@xw.arg('endD', np.array, ndim=2)
@xw.arg('heads', np.array, ndim=2)
#@xw.ret(expand='table')   
def testBLP(heads, spot,fwd,startD,endD):
 """xlwings User Define Function
    Can be imported to Excel document
 """
    try:
        heads=removeUni(heads[0])
        #print heads
        Keys=['Spot', 'Fwd3m'] # default keys setting
        flds=["PX_LAST"] # default field setting
        spot=removeUni(spot[0]) 
        fwd=removeUni(fwd.tolist()[0])
        Values=[spot,fwd] 
        start=str(startD.tolist()[0][0])
        #print start
        end=str(endD.tolist()[0][0])
        #print end
        Inputs_dict=dict(zip(Keys,Values)) # Create input dictionary
        #print Inputs_dict
        df_dict={}
        # Get dictionary of Desired DataFrames from Bloomberg API and Merge together
        for key,value in Inputs_dict.items(): 
            df_dict[key]=DF_Merge(key,value,heads,flds,start,end)
        #print df_dict
        # Create connection with Access Database
        conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; '
                'DBQ=C:\\Test.accdb;')
        # Build_Access_Connect is a function from testAccess.py
        [crsr,cnxn]=testAccess.Build_Access_Connect(conn_str)
        # write results to database
        pd2DB(df_dict, crsr)
        cnxn.commit() 
        # get update tables from database and convert to a dict of dateframes
        df_dict=testAccess.Tables2DF(crsr)
        # analyse is a function in testAccess.py
        [roll_down, z_score_rd, carry, z_score, tr]=testAccess.analyse(df_dict)
        cnxn.close()
        #print roll_down, z_score, carry, z_score_rd, tr
        # Insert Names to each result list
        roll_down.insert(0,"Roll down")
        z_score_rd.insert(0,"z_score_rd")
        carry.insert(0,"carry")
        z_score.insert(0,"z_score")
        tr.insert(0,"Total Return")
        #print roll_down, z_score, carry, z_score_rd, tr
        return roll_down, z_score, carry, z_score_rd, tr
    except: # If any error occurs, return eroor
        return "Error"
        #cnxn.commit()
        #cnxn.close()
        
    
    
'''
if __name__ == "__main__":
    print "HistoryDataExtraction"
    try:
       Keys=['Spot', 'Fwd3m']
       Values=[['USSWC CMPN Curncy','USSWF CMPN Curncy','USSWAP1 CMPN Curncy',
                'USSWAP2  CMPN Curncy','USSWAP3  CMPN Curncy',
                'USSWAP5  CMPN Curncy','USSWAP10 CMPN Curncy'], 
                ['USFS0CC  BLC Curncy','USFS0CF  BLC Curncy',
                 'USFS0C1  BLC Curncy','USFS0C2  BLC Curncy',
                 'USFS0C3  BLC Curncy','USFS0C5  BLC Curncy',
                 'USFS0C10 BLC Curncy']]
       flds=["PX_LAST"]
       start="20070101"
       end="20170823"
                                
       heads=['3m','6m','1y','2y', '3y','5y','10y']
       
       Inputs_dict=dict(zip(Keys,Values))
       df_dict={}
       for key,value in Inputs_dict.items():
           df_dict[key]=DF_Merge(key,value,heads,flds,start,end)
       #print df_dict
       #data=bdh(["IBM US Equity","MSFT US Equity","AAPL US Equity"], ["PX_LAST","OPEN","VWAP_VOLUME"], "20170101","20170120")
       #print data
       conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; '
                   'DBQ=C:\\Test.accdb;')
       
       srcDB = 'C:\\Test.accdb'
       destDB = 'C:\\Test_backup.accdb'
       
       #testAccess.Repair_Compact_DB(srcDB, destDB) # uncomment to repair and compact database 
       [crsr,cnxn]=testAccess.Build_Access_Connect(conn_str) 
      
       pd2DB(df_dict, crsr)
       
       cnxn.commit()
       cnxn.close()
       
       
    except :
        print "Ctrl+C pressed. Stopping..."
        cnxn.commit()
        cnxn.close()'''
