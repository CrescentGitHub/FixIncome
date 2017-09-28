
import xlwings as xw
import pandas as pd
import numpy as np
import pyodbc
from dateutil.relativedelta import relativedelta
from YieldCurve import YieldCurve
from UtilityClass import UtilityClass
from SpotCurve import SpotCurve
import BLP2DF
import datetime


@xw.func
@xw.arg('Tickers', pd.DataFrame, index=True, header=True)
@xw.arg('start', np.array, ndim=2)
def updateDB(Tickers,start):
    headers=Tickers.index
    table_names=BLP2DF.removeUni(list(Tickers))
    tickers_list=Tickers.T.values.tolist()
    for i,each in enumerate(tickers_list):
        tickers_list[i]=BLP2DF.removeUni(each)
    flds=["PX_LAST"]
    #start=str(int(start[0][0]))
    start=(datetime.date.today()-datetime.timedelta(days=60)).strftime('%Y%m%d')
    print start
    data={}
    for name, tickers in zip(table_names,tickers_list):
        data[name]=BLP2DF.DF_Merge(tickers,headers,flds,start)
    conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; '
                'DBQ=C:\\Test.accdb;')
    [crsr,cnxn]=Build_Access_Connect(conn_str)
    BLP2DF.pd2DB(data, crsr)
    cnxn.commit() 
    cnxn.close()

@xw.func
@xw.ret(expand='table')
def FwdPlot(Country,db_str):
    """ Return "1y/1y-1y" DataFrame of Country
    db_str: database directory
    """
    fwd=str(Country)+"Fwd1y"  # Construct 1 year forward table name
    spot=str(Country)+"Spot"  # Construct spot table name
    db_str= 'DBQ='+str(db_str)  
    conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + db_str)
    [crsr,cnxn]=Build_Access_Connect(conn_str)  # Connect to MS Access
    df=Tables2DF(crsr,spot,fwd)  # return dictionary of tables from database
    fwd=df[fwd]  # get forward table from dictionary
    spot=df[spot]  # get spot table from dictionary
    tenors=list(spot)  # get tenor headers from spot table
    t='1y'  
    
    indx=spot.index.tolist()  
    indx_fwd=fwd.index.tolist()
    dels=[]
    
    if t in tenors: # no need to interpolate for 1y point
        r=[]
        for each in indx:
            if each in indx_fwd: # match dates between forward and spot
                r.append(fwd.loc[each].to_dict()[t]-spot.loc[each].to_dict()[t])
            else:
                dels.append(each) 
        for each in dels:  # delete spot dates that are not in forward dates
            indx.remove(each)
    else: # interpolation is needed for 1y point
        r=[]
        for each in indx:
            if each in indx_fwd:  # Match dates between spot and forward dates
                f=fwd.loc[each].tolist()
                s=spot.loc[each].tolist()
                f_kwarg=dict(zip(tenors,f))
                s_kwarg=dict(zip(tenors,s))
                y1=YieldCurve(**f_kwarg)  # forward interpolation for 1y point
                y2=YieldCurve(**s_kwarg)  # spot interpolation for 1y point
                r.append(y1.build_curve(1)-y2.build_curve(1)) # calc spread
            else:
                dels.append(each)
            
        for each in dels:
                indx.remove(each)
   
    rlt=pd.DataFrame(r,index=indx,columns=['1y/1y-1y'])  # Construct a dataframe
    #  Add average value column
    rlt['Aver']=[np.mean(rlt['1y/1y-1y'].tolist())]*len(rlt['1y/1y-1y'].tolist())
    sd=np.std(rlt['1y/1y-1y'].tolist())
    rlt['+1sd']=[rlt['Aver'].values[0]+sd]*len(rlt['1y/1y-1y'].tolist())  #  1 std above average
    rlt['-1sd']=[rlt['Aver'].values[0]-sd]*len(rlt['1y/1y-1y'].tolist())  #  1 std below average
    rlt['+2sd']=[rlt['Aver'].values[0]+2*sd]*len(rlt['1y/1y-1y'].tolist())  #  2 std above average
    rlt['-2sd']=[rlt['Aver'].values[0]-2*sd]*len(rlt['1y/1y-1y'].tolist())  #  2 std below average
    return rlt


def Build_Access_Connect(conn_str):
    """Build Connnection with Access DataBase
    Argument:
    conn_str  ---a string contains Driver and file Path
    Output:
    cnxn  ---connection
    crsr  ---cursor
    """
    cnxn = pyodbc.connect(conn_str)
    crsr = cnxn.cursor()
    return crsr,cnxn

def Tables2DF(crsr,*selected_table_name,**LookBackWindow):
    """Reformat Tables in DataBase to Pandas DataFrame and Stored in a dictionary with table_names as keys
    Argument:
    crsr                  ---cursor from access
    *selected_table_name  ---table names in string format e.g "Spot", return all tables if ommited
    **LookBackWindow      ---Select part of the data regarding with LookBackWindow, return full range if ommitted
                          Possible Values: '1y','2y','3y','4y','5y','10y'
    Output:
    Dictionary of DataFrames with table_names as keys
    """
    dict_Para={'1y':1,'2y':2,'3y':3,'4y':4,'5y':5,'10y':10} # used to convert LookBackWindow to number format
    db_schema = dict() # used to save table names and table column names of all tables in database
    tbls = crsr.tables(tableType='TABLE').fetchall()  
    for tbl in tbls:
        if tbl.table_name not in db_schema.keys(): 
            db_schema[tbl.table_name] = list()
        for col in crsr.columns(table=tbl.table_name):
            db_schema[tbl.table_name].append(col[3])
                
    if selected_table_name==() and LookBackWindow=={}: # Return all tables 
        df_dict=dict()
        for tbl, cols in db_schema.items():
            sql = "SELECT * from %s" % tbl  
            crsr.execute(sql)
            val_list = []
            while True: # Fetch lines from database
                row = crsr.fetchone()
                if row is None:
                    break
                val_list.append(list(row))
            temp_df = pd.DataFrame(val_list, columns=cols) #Convert to dataframe format
            temp_df.set_index(keys=cols[0], inplace=True) # First Column as Key
            df_dict[tbl]=temp_df # Save each dataframe in dictionary
        return df_dict
            
    elif selected_table_name==() and LookBackWindow!={}: # Return part of each table in database
        LB=LookBackWindow.values()[0] 
        df_dict={}
        tbls_names=db_schema.keys()  # extract all table names
        for each in tbls_names:  # select part of the database     
            idx_last=crsr.execute("select top 1 [Date] from "+str(each)+" order by [Date] desc").fetchone()[0]  # select part of the database     
            dd=idx_last-relativedelta(years=dict_Para[LB])  #Compute the begining date of periodgit
            crsr.execute("select * from "+str(each)+" where [Date]>=?", dd)  #Select all data later than begining date
            val_list = []  #Fetch all data
            while True:
                row = crsr.fetchone()
                if row is None:
                    break
                val_list.append(list(row))
            header=db_schema[each] # get column names of database
            temp_df = pd.DataFrame(val_list, columns=header)
            temp_df.set_index(keys=header[0], inplace=True) # First Column [Date] as Key
            df_dict[each]=temp_df # return dictionary of dataframes
        return df_dict
        
    elif selected_table_name!=() and LookBackWindow=={}:  # Return full range of selected tables
         df_dict=dict()
         for each in selected_table_name: # Extract tables one by one
             sql = "SELECT * from %s" % each  
             crsr.execute(sql)
             val_list = []
             while True:  # Fetch lines
                 row = crsr.fetchone()
                 if row is None:
                     break
                 val_list.append(list(row))
             temp_df = pd.DataFrame(val_list, columns=db_schema[each]) # Create a dataframe
             temp_df.set_index(keys=db_schema[each][0], inplace=True) # First Column as Key
             df_dict[each]=temp_df
         return df_dict
    else:  # Return part of the selected tables
         LB=LookBackWindow.values()[0]
         df_dict=dict()
         for each in selected_table_name:
             idx_last=crsr.execute("select top 1 [Date] from "+str(each)+" order by [Date] desc").fetchone()[0]  # select part of the database     
             dd=idx_last-relativedelta(years=dict_Para[LB])  #Compute the begining date of periodgit
             crsr.execute("select * from "+str(each)+" where [Date]>=?", dd)  #Select all data later than begining date
             val_list = []  #Fetch all data
             while True:
                 row = crsr.fetchone()
                 if row is None:
                     break
                 val_list.append(list(row))
             header=db_schema[each] # get column names of database
             temp_df = pd.DataFrame(val_list, columns=header)
             temp_df.set_index(keys=header[0], inplace=True) # First Column [Date] as Key
             df_dict[each]=temp_df # return dictionary of dataframes
         return df_dict

@xw.func
@xw.arg('TableList', np.array, ndim=2)
def calc_historic_vol(tenors,TableList, df_list,frequency='d'):
    """calc historical volatility of each table in df_list
    tenors: tenor headers of each table
    TableList: a list containing all tables in df_list
    df_list: a dictionary containing spot and forward tables
    frequency: frequency of data in df_list tables. default as daily data
    Output: dictionary of volatility dataframe
    """
    
    ttt={}
    frequency_dict={'d':252,'w':52, 'm':12, 'a':1}
    for each in TableList:
        idx=df_list[each].index[1:]
        for i,col in enumerate(tenors):
            timeseries=df_list[each][col].values.tolist()
            dyields=[(timeseries[x+1]-timeseries[x]) for x in range(len(timeseries)-1)]
            if i==0: # Create a DateFrame
                rlt=pd.DataFrame(dyields,index=idx,columns=['dy'])
                rlt[col] = rlt['dy'].rolling(window=66).std()*np.sqrt(frequency_dict[frequency])  # annulized three months rolling window std
                rlt.drop('dy',1,inplace=True)
            else:  # Create a Series and integrate to the dataframe
                rlt.loc[:,'dy']=pd.Series(dyields,index=idx)
                rlt[col] = rlt['dy'].rolling(window=66).std()*np.sqrt(frequency_dict[frequency])  # annulized three months rolling window std
                rlt.drop('dy',1,inplace=True)
        rlt = rlt.dropna()
        ttt[each]=rlt
    return ttt



@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def SpreadsTable(db_str, LookBackWindow,TableList):
    """Return Today, 1week before and 1month before's Spreads Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
        TableList: a list of tables needed
    Output: Today, 1week and 1month's spreads level,zscore(asymmetric) and percentile    
    """
    tttt=datetime.datetime.now()
    Convert_dict={'2s5s':[2,5],'5s10s':[5,10],'2s10s':[2,10],'1s2s':[1,2],'2s3s':[2,3],'1s3s':[1,3],'3s5s':[3,5],'5s7s':[5,7]}
    [rlt_headers,df_list,headers,cnxn,TableList]=GenHnInDF(db_str,TableList,LookBackWindow)
    spreads=['2s5s','5s10s','2s10s','1s2s','2s3s','1s3s','3s5s','5s7s']  # desired spreads
    temp2=[]
    
    for t in spreads:  # Construct index for result spreads
        temp2=temp2+[t]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(spreads))]
    
    
    Values=[] 
    u=UtilityClass() 
    
    tenors=[]
    for each in spreads:  # Convert and merge all spreads into one list
        for t in Convert_dict[each]:
            tenors.append(t)
        
    for tbl in TableList:  # Compute spreads for each table
        indx = df_list[tbl].index  # get index
        vals_list = df_list[tbl].values.tolist() 
        s=[]
        for vals in vals_list: # for each curve, compute spread between t1 and t2 
            kwarg = dict(zip(headers, vals))
            yieldcurve = YieldCurve(**kwarg)
            yields=yieldcurve.build_curve(tenors)
            s.append([x-y for x,y in zip(yields[1::2],yields[0::2])])
        spread_pd=pd.DataFrame(s, index=indx,columns=spreads)
        lvl=[]
        z=[]
        p=[]
        for each in spreads: # for each column in spread dataframe, compute zscore and percentile
            ss=spread_pd[each].to_frame()
            [s_lvl,s_zscore]=u.calc_z_score(ss,False,'1w','1m')
            s_ptl=u.calc_percentile(ss,'1w','1m')
            lvl=lvl+s_lvl
            z=z+s_zscore
            p=p+s_ptl
        Values.append(lvl)
        Values.append(z)
        Values.append(p)
    tt=np.asarray(Values) 
    rlt = pd.DataFrame(tt, index=rlt_headers, columns =Index) # Construct result dataframe  
    rlt=rlt.T
    cnxn.close()
    print datetime.datetime.now()-tttt # print time needed running this function
    return rlt
 
    
@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def SpreadsRDTable(db_str, LookBackWindow,TableList):
    """For Spot Curves, return Spread Total Return
    For Forward Curves, return Spread Roll Down
    db_str: database file directory
    LookBackWindow: Whether to select part of the table
    TableList: a list of tables needed"""
    
    tttt=datetime.datetime.now()
    Convert_dict={'2s5s':['2y','5y'],'5s10s':['5y','10y'],'2s10s':['2y','10y'],'1s2s':['1y','2y'],'2s3s':['2y','3y'],'1s3s':['1y','3y'],'3s5s':['3y','5y'],'5s7s':['5y','7y']}
    
    [rlt_headers,df_list,headers,cnxn,TableList]=GenHnInDF(db_str,TableList,LookBackWindow)
    spreads=['2s5s','5s10s','2s10s','1s2s','2s3s','1s3s','3s5s','5s7s']
    temp2=[]

    for t in spreads:    # Construct result dateframe index
        temp2=temp2+[t]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(spreads))]
    
    Values=[] 
    u=UtilityClass() 
    
    tenors=[]
    for each in spreads:
        tenors=tenors+Convert_dict[each]
    
    prd = ['3m'] * len(tenors)
    for each in TableList:
        if each.endswith("Spot"):  # Find Spot curves' table name and index
            spottbl=each
            spot_idx=df_list[each].index.tolist()
        if each.endswith("3m"):  # Find 3m Forward curves' table name and index
            f3tbl=each
            f3_idx=df_list[each].index.tolist()
            
    for tbl in TableList:  # iterate through all tables
        indx=df_list[tbl].index.tolist()
        r=[]
        dels=[]
        for each in indx:
            if tbl.endswith("Spot"):  # For spot curves, compute spread total return
                if each in f3_idx:
                    s_dict = df_list[tbl].loc[each].to_dict()
                    f_dict = df_list[f3tbl].loc[each].to_dict()
                    SC = SpotCurve(s_dict,f_dict)
                    tr=SC.calc_total_return(tenors,prd)
                    r.append([x-y for x,y in zip(tr[1::2],tr[0::2])])
                else: dels.append(each)
            else:
                if each in spot_idx:  # For forward curves, compute spread roll down
                    s_dict = df_list[spottbl].loc[each].to_dict()
                    f_dict = df_list[tbl].loc[each].to_dict()
                    yy = YieldCurve(**f_dict)
                    tr=yy.calc_roll_down(tenors,prd,s_dict,tbl[-2:])
                    r.append([x-y for x,y in zip(tr[1::2],tr[0::2])])
                else: dels.append(each)
        for each in dels:
            indx.remove(each)
        spread_rd_pd=pd.DataFrame(r, index=indx,columns=spreads)  # Construct a spread TR dataframe
        lvl=[]
        z=[]
        p=[]
        for each in spreads:  # for each spread TR, compute level,zscore and percentile
            ss=spread_rd_pd[each].to_frame()
            [s_lvl,s_zscore]=u.calc_z_score(ss,False,'1w','1m')
            s_ptl=u.calc_percentile(ss,'1w','1m')
            lvl=lvl+s_lvl
            z=z+s_zscore
            p=p+s_ptl
        Values.append(lvl)
        Values.append(z)
        Values.append(p)
    tt=np.asarray(Values) 
    rlt = pd.DataFrame(tt, index=rlt_headers, columns =Index )  # Resulted Dataframe
    rlt=rlt.T
    cnxn.close()
    print datetime.datetime.now()-tttt  # print time needed running the function
    return rlt




@xw.func
@xw.arg('TableList', np.array, ndim=2)
def ButterFlysTable(db_str, LookBackWindow,TableList):
    """Return Today, 1week before and 1month before's Flys Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
        TableList: a list of tables needed
    """
    tttt=datetime.datetime.now()
    Convert_dict={'2s5s10s':[2,5,10],'5s7s10s':[5,7,10],'1s3s5s':[1,3,5],'3s5s7s':[3,5,7],'1s2s3s':[1,2,3]}
    [rlt_headers,df_list,headers,cnxn,TableList]=GenHnInDF(db_str,TableList,LookBackWindow)
    flys=['2s5s10s','5s7s10s','1s3s5s','3s5s7s','1s2s3s']
    
    temp2=[]
    for t in flys:    
        temp2=temp2+[t]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(flys))]
    
    Values=[]
    u=UtilityClass()
    
    tenors=[]
    for each in flys:
        tenors=tenors+Convert_dict[each]
    
    for tbl in TableList:
        indx = df_list[tbl].index  # get index
        vals_list = df_list[tbl].values.tolist() 
        s=[]
        for vals in vals_list: # for each curve, compute spread between t1 and t2 
            kwarg = dict(zip(headers, vals))
            yieldcurve = YieldCurve(**kwarg)
            yields=yieldcurve.build_curve(tenors)
            s.append([2*y-z-x for x,y,z in zip(yields[0::3],yields[1::3],yields[2::3])])
        fly_pd=pd.DataFrame(s, index=indx,columns=flys)
        lvl=[]
        z=[]
        p=[]
        for each in flys: # For each fly, compute last data level,zscore and percentile
            ss=fly_pd[each].to_frame()
            [s_lvl,s_zscore]=u.calc_z_score(ss,False,'1w','1m')
            s_ptl=u.calc_percentile(ss,'1w','1m')
            lvl=lvl+s_lvl
            z=z+s_zscore
            p=p+s_ptl
        Values.append(lvl)
        Values.append(z)
        Values.append(p)
    tt=np.asarray(Values) 
    rlt = pd.DataFrame(tt, index=rlt_headers, columns =Index )
    rlt=rlt.T
    cnxn.close()
    print datetime.datetime.now()-tttt
    return rlt


@xw.func
@xw.arg('TableList', np.array, ndim=2)
def RollDownTable(db_str, LookBackWindow,TableList):
    """Return Today, 1week before and 1month before's RollDown, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
        TableList: a list of tables needed
    """
    tttt=datetime.datetime.now()
    [headers,df_list,tenors,cnxn,TableList]=GenHnInDF(db_str,TableList,LookBackWindow)
    
    temp2=[]
    for i in range(len(tenors)-1):    
        temp2=temp2+[tenors[i+1]]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*(len(tenors)-1))]
    u=UtilityClass()

    prd = ['3m'] * (len(tenors)-1)
    
    for each in TableList:
        if each.endswith("Spot"):
            spottbl=each
            spot_vals=df_list[each].values.tolist()
            spot_idx=df_list[each].index.tolist()
    
    Values=[]
    for tbl in TableList:
        if tbl.endswith("Spot"):
            roll_down_list = []
            for vals in spot_vals:
                kwarg = dict(zip(tenors, vals))
                yieldcurve = YieldCurve(**kwarg)
                rd = yieldcurve.calc_roll_down(tenors[1:], prd)
                roll_down_list.append(rd)
            df_roll_down = pd.DataFrame(roll_down_list, index=spot_idx,columns=tenors[1:]) 
            
        else:
            f=tbl[-2:]
            roll_down_list = []
            indx=df_list[tbl].index.tolist()
            dels=[]
            for each in indx:
                if each in spot_idx:
                    s=df_list[spottbl].loc[each].to_dict()
                    kwarg=df_list[tbl].loc[each].to_dict()
                    y=YieldCurve(**kwarg)
                    rd=y.calc_roll_down(tenors[1:],prd,s,f)
                    roll_down_list.append(rd)
                else: 
                    dels.append(each)
            for each in dels:
                indx.remove(each)
            df_roll_down = pd.DataFrame(roll_down_list, index=indx,columns=tenors[1:]) 
            
        lvl=[]
        z=[]
        p=[]
        for each in tenors[1:]:  
            temp_rd=df_roll_down[each].to_frame() # For each column, create a df and pass to calc z score and percentile
            [rd_lvl,rd_zscore]=u.calc_z_score(temp_rd,False,'1w','1m')
            rd_ptl=u.calc_percentile(temp_rd,'1w','1m')
            lvl=lvl+rd_lvl
            z=z+rd_zscore
            p=p+rd_ptl
        Values.append(lvl)
        Values.append(z)
        Values.append(p)
    tt=np.asarray(Values) 
    rlt = pd.DataFrame(tt, index=headers, columns =Index )
    rlt=rlt.T
    cnxn.close()
    print datetime.datetime.now()-tttt
    return rlt
    
@xw.func
@xw.arg('TableList', np.array, ndim=2)
def AdjRollDownTable(db_str, LookBackWindow,TableList):
    """Return Today, 1week before and 1month before's Adj_RollDown, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
    """
    tttt=datetime.datetime.now()
    [headers,df_list,tenors,cnxn,TableList]=GenHnInDF(db_str,TableList,LookBackWindow)
    vol_dict=calc_historic_vol(tenors,TableList, df_list)

    temp2=[]
    for i in range(len(tenors)-1):    
        temp2=temp2+[tenors[i+1]]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*(len(tenors)-1))]
    u=UtilityClass()

    prd = ['3m'] * (len(tenors)-1)
    
    for each in TableList:
        if each.endswith("Spot"):
            spottbl=each
            spot_vals=df_list[each].values.tolist()
            spot_idx=df_list[each].index.tolist()
    
    Values=[]
    for tbl in TableList:
        if tbl.endswith("Spot"):
            roll_down_list = []
            for vals in spot_vals:
                kwarg = dict(zip(tenors, vals))
                yieldcurve = YieldCurve(**kwarg)
                rd = yieldcurve.calc_roll_down(tenors[1:], prd)
                roll_down_list.append(rd)
            df_roll_down = pd.DataFrame(roll_down_list, index=spot_idx,columns=tenors[1:]) 
            
        else:
            f=tbl[-2:]
            roll_down_list = []
            indx=df_list[tbl].index.tolist()
            dels=[]
            for each in indx:
                if each in spot_idx:
                    s=df_list[spottbl].loc[each].to_dict()
                    kwarg=df_list[tbl].loc[each].to_dict()
                    y=YieldCurve(**kwarg)
                    rd=y.calc_roll_down(tenors[1:],prd,s,f)
                    roll_down_list.append(rd)
                else: 
                    dels.append(each)
            for each in dels:
                indx.remove(each)
            df_roll_down = pd.DataFrame(roll_down_list, index=indx,columns=tenors[1:]) 
        lvl=[]
        z=[]
        p=[]
        
        for each in tenors[1:]:
            df_vol=vol_dict[tbl]
            start=df_vol.index[0]
            df=df_roll_down.loc[start :]
            if not tbl.endswith("Spot"):
                df_vol=df_vol.loc[df.index]
            vols=df_vol[each].tolist()
            rd=df[each].tolist()
            adj_rd=[x/yy for x,yy in zip(rd,vols)]
            temp_adj_rd=pd.DataFrame(adj_rd,index=df.index) # For each column, create a df and pass to calc z score and percentile
            [rd_lvl,rd_zscore]=u.calc_z_score(temp_adj_rd,False,'1w','1m')
            rd_ptl=u.calc_percentile(temp_adj_rd,'1w','1m')
            lvl=lvl+rd_lvl
            z=z+rd_zscore
            p=p+rd_ptl
        Values.append(lvl)
        Values.append(z)
        Values.append(p)
    tt=np.asarray(Values) 
    rlt = pd.DataFrame(tt, index=headers, columns =Index )
    rlt=rlt.T
    cnxn.close()
    print datetime.datetime.now()-tttt
    return rlt

@xw.func
@xw.arg('TableList', np.array, ndim=2)
def CarryTable(db_str, LookBackWindow, TableList):
    """Return Today, 1week before and 1month before's Carry Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
    """
    tttt=datetime.datetime.now()
    TableList=BLP2DF.removeUni(np.delete(TableList[0], 0))
    db_str= 'DBQ='+str(db_str)
    conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + db_str)
    [crsr,cnxn]=Build_Access_Connect(conn_str)
    
    Tbls=[TableList[0],TableList[1]]
    if str(LookBackWindow)!="ALL":
        df_list=Tables2DF(crsr,*Tbls,LB=str(LookBackWindow))
    else: df_list=Tables2DF(crsr,*Tbls)
    tenors = list(df_list.values()[0])

    vol_dict=calc_historic_vol(tenors,Tbls, df_list)
    
    vol_start=vol_dict[Tbls[0]].index[0]
    spot=df_list[Tbls[0]].loc[vol_start :]
    fwd=df_list[Tbls[1]].loc[vol_start :]
    u=UtilityClass()
    
    indx = spot.index.tolist()
    indx_fwd=fwd.index.tolist()
    
    temp2=[]
    for i in range(len(tenors)-1):    
        temp2=temp2+[tenors[i+1]]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*(len(tenors)-1))]
    Headers=[np.array(["3mCarry"]*3+["Adj 3mCarry"]*3),np.array(['Level', 'Z', 'PCTL']*2)]
    prd = ['3m'] * (len(tenors)-1)
    dels=[]
    carry_list = []
    for each in indx:
        if each in indx_fwd:
            s = spot.loc[each].tolist()
            f = fwd.loc[each].tolist()
            s_dict = dict(zip(tenors, s))
            f_dict = dict(zip(tenors, f))
            SC = SpotCurve(s_dict,f_dict)
            carry_list.append(SC.calc_carry(tenors[1:], prd))
        else:
            dels.append(each)
    for each in dels:
        indx.remove(each)
    df_carry = pd.DataFrame(carry_list, index=indx,columns=tenors[1 :]) 
    Values=[]
    for each in tenors[1 :]:
        c=df_carry[each].tolist()
        v=vol_dict[Tbls[0]][each].tolist()
        adj_c=[x/y for x,y in zip(c,v)]
        temp_c=pd.DataFrame(c,index=indx)
        temp_adj_c=pd.DataFrame(adj_c,index=indx)
        [lvl,zscore]=u.calc_z_score(temp_c,False,'1w','1m')
        ptl=u.calc_percentile(temp_c,'1w','1m')
        [adj_lvl,adj_zscore]=u.calc_z_score(temp_adj_c,False,'1w','1m')
        adj_ptl=u.calc_percentile(temp_adj_c,'1w','1m')
        for i in range (len(lvl)):
            row=[]
            row=[lvl[i]]+[zscore[i]]+[ptl[i]]+[adj_lvl[i]]+[adj_zscore[i]]+[adj_ptl[i]]
            Values.append(row)
    tt=np.asarray(Values)
    rlt = pd.DataFrame(tt, index=Index, columns =Headers )
    cnxn.close()
    print datetime.datetime.now()-tttt
    return rlt


@xw.func
@xw.arg('TableList', np.array, ndim=2)
def TRTable(db_str, LookBackWindow, TableList):
    """Return Today, 1week before and 1month before's Total Return Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
    """
    tttt=datetime.datetime.now()
    TableList=BLP2DF.removeUni(np.delete(TableList[0], 0))
    db_str= 'DBQ='+str(db_str)
    conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + db_str)
    [crsr,cnxn]=Build_Access_Connect(conn_str)
    
    Tbls=[TableList[0],TableList[1]]
    if str(LookBackWindow)!="ALL":
        df_list=Tables2DF(crsr,*Tbls,LB=str(LookBackWindow))
    else: df_list=Tables2DF(crsr,*Tbls)
    
    tenors = list(df_list.values()[0])
    vol_dict=calc_historic_vol(tenors,Tbls, df_list)
    vol_start=vol_dict[Tbls[0]].index[0]
    spot=df_list[Tbls[0]].loc[vol_start :]
    fwd=df_list[Tbls[1]].loc[vol_start :]
    u=UtilityClass()
    
    indx = spot.index.tolist()
    indx_fwd=fwd.index.tolist()
    
    temp2=[]
    for i in range(len(tenors)-1):    
        temp2=temp2+[tenors[i+1]]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*(len(tenors)-1))]
    Headers=[np.array(["3mTR"]*3+["Adj 3mTR"]*3),np.array(['Level', 'Z', 'PCTL']*2)]
    prd = ['3m'] * (len(tenors)-1)
    
    dels=[]
    TR_list = []
    for each in indx:
        if each in indx_fwd:
            s = spot.loc[each].tolist()
            f = fwd.loc[each].tolist()
            s_dict = dict(zip(tenors, s))
            f_dict = dict(zip(tenors, f))
            SC = SpotCurve(s_dict,f_dict)
            TR_list.append(SC.calc_total_return(tenors[1:], prd))
        else:
            dels.append(each)
    for each in dels:
        indx.remove(each)
    df_TR = pd.DataFrame(TR_list, index=indx,columns=tenors[1 :]) 
    Values=[]
    for each in tenors[1 :]:
        tr=df_TR[each].tolist()
        v=vol_dict[Tbls[0]][each].tolist()
        adj_tr=[x/y for x,y in zip(tr,v)]
        temp_tr=pd.DataFrame(tr,index=indx)
        temp_adj_tr=pd.DataFrame(adj_tr,index=indx)
        [lvl,zscore]=u.calc_z_score(temp_tr,False,'1w','1m')
        ptl=u.calc_percentile(temp_tr,'1w','1m')
        [adj_lvl,adj_zscore]=u.calc_z_score(temp_adj_tr,False,'1w','1m')
        adj_ptl=u.calc_percentile(temp_adj_tr,'1w','1m')
        for i in range (len(lvl)):
            row=[]
            row=[lvl[i]]+[zscore[i]]+[ptl[i]]+[adj_lvl[i]]+[adj_zscore[i]]+[adj_ptl[i]]
            Values.append(row)
    tt=np.asarray(Values)
    rlt = pd.DataFrame(tt, index=Index, columns =Headers )
    cnxn.close()
    print datetime.datetime.now()-tttt
    return rlt
    

def GenHnInDF(db_str,TableList, LookBackWindow):
    TableList=BLP2DF.removeUni(np.delete(TableList[0], 0))
    db_str= 'DBQ='+str(db_str)   
    conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + db_str)  #Create database connection string
    [crsr,cnxn]=Build_Access_Connect(conn_str) #Build Connection with database
    
    if str(LookBackWindow)!="ALL":
        df_list=Tables2DF(crsr,*list(TableList),LB=str(LookBackWindow))
    else: df_list=Tables2DF(crsr,*list(TableList))
    
    tenors = list(df_list.values()[0])
    temp1=[]
    for tbl in TableList:
        temp1=temp1+[tbl]*3
        
    headers = [np.array(temp1), np.array(['Level', 'Z', 'PCTL']*len(TableList))]
    return headers,df_list,tenors,cnxn,TableList

@xw.func
@xw.arg('TableList', np.array, ndim=2)
def YieldsLvLs(db_str,LookBackWindow,TableList):
    tttt=datetime.datetime.now()
    [headers,df_list,tenors,cnxn,TableList]=GenHnInDF(db_str,TableList,LookBackWindow)
    temp2=[]
    for t in tenors:    
        temp2=temp2+[t]*3
    Index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(tenors))]
    u=UtilityClass()
    
    Values=[]
    for each in tenors:
        for i in range(3):
            row=[]
            for tbl in TableList:
                indx = df_list[tbl].index
                s=df_list[tbl][each].tolist()
                s=pd.DataFrame(s,index=indx)
                [lvl,zscore]=u.calc_z_score(s,False,'1w','1m')
                ptl=u.calc_percentile(s,'1w','1m')
                row.append(lvl[i])
                row.append(zscore[i])
                row.append(ptl[i])
            Values.append(row)
    
    tt=np.asarray(Values)
    rlt = pd.DataFrame(tt, index=Index, columns =headers )
    cnxn.close()
    print datetime.datetime.now()-tttt
    return rlt


if __name__ == "__main__":
    conn_str = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; '
                'DBQ=C:\\Test.accdb;')
    dbstr='C:\\Test.accdb;'
    LB='1y'
    ttt=['','KRWSpot','KRWFwd3m','KRWFwd6m','KRWFwd1y','KRWFwd2y','KRWFwd3y','KRWFwd4y','KRWFwd5y']
    #s= calc_historic_vol(dbstr,LB)
    #CarryTable(dbstr, LB, s)
    SpreadsTable(dbstr,LB,ttt)
    print datetime.datetime.now()-s
    
    #print TRTable(dbstr,LB)

    ##Tables2DF(crsr,LB='2y')
    
