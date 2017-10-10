
import xlwings as xw
import pandas as pd
import numpy as np
import pyodbc
from dateutil.relativedelta import relativedelta
from YieldCurve import YieldCurve
from UtilityClass import UtilityClass
import datetime
import os
import win32com.client


@xw.func
@xw.ret(expand='table')
def FwdPlot(Country,path):
    """ Return "1y/1y-1y" DataFrame of Country
    db_str: database directory
    """
    print path
    fwd=str(Country)+"Fwd1y"  # Construct 1 year forward table name
    spot=str(Country)+"Spot"  # Construct spot table name
    YldsDB1= 'DBQ='+str(path+ '\\YieldsData.accdb')
    conn1 = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + YldsDB1)
    [crsr1,cnxn1]=Build_Access_Connect(conn1)  # Connect to MS Access
    crsrs=[(crsr1,cnxn1)]
    df=Tables2DF(crsrs,spot,fwd)  # return dictionary of tables from database
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

def removeUni(l):
    """convert unicode to string"""
    result=[]
    for each in l:
        each=each.replace(u'\xa0', ' ').encode('utf-8')
        result.append(each)
    return result

def Tables2DF(crsrs,*selected_table_name,**LookBackWindow):
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
    
    crsr=crsrs[0][0]
    cnxn=crsrs[0][1]
    
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
            df_dict[tbl]=temp_df.sort_index() # Save each dataframe in dictionary
        cnxn.close() 
        return df_dict
            
    elif selected_table_name==() and LookBackWindow!={}: # Return part of each table in database
        LB=LookBackWindow.values()[0] 
        df_dict={}
        tbls_names=db_schema.keys()  # extract all table names
        for each in tbls_names:  # select part of the database     
            idx_last=crsr.execute("select top 1 [Date] from "+str(each)+" order by [Date] desc").fetchone()[0]  # select part of the database     
            if LB=='2m':
                dd=idx_last-relativedelta(days=61)
            else:
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
            df_dict[each]=temp_df.sort_index() # return dictionary of dataframes
        cnxn.close()
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
             df_dict[each]=temp_df.sort_index()
         cnxn.close()
         return df_dict
    else:  # Return part of the selected tables
         LB=LookBackWindow.values()[0]
         df_dict=dict()
         for each in selected_table_name:
             idx_last=crsr.execute("select top 1 [Date] from "+str(each)+" order by [Date] desc").fetchone()[0]  # select part of the database     
             if LB=='2m':
                 dd=idx_last-relativedelta(days=61)
             else:
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
             df_dict[each]=temp_df.sort_index() # return dictionary of dataframes
         cnxn.close() 
         return df_dict


@xw.func
def Repair_Compact_DB(path):
    """Repair and Compact the DataBase"""
    oApp = win32com.client.Dispatch("Access.Application")
    srcDB=str(path+'\\TempData.accdb')
    destDB = str(path+'\\TempData_backup.accdb')
    oApp.compactRepair(srcDB,destDB)
    os.remove(destDB)
    oApp = None


def GetTbls(TableList,LookBackWindow,tblsuffix,path):
    TableList=removeUni(np.delete(TableList[0], 0))
    tbls=[]
    for each in TableList:
        tbls.append(each+tblsuffix)
    
    tempDB= 'DBQ='+str(path+'\\TempData.accdb')   
    conn = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + tempDB)  #Create database connection string
    [crsr,cnxn]=Build_Access_Connect(conn)
    
    
    crsrs=[(crsr,cnxn)]
    
    if str(LookBackWindow)!="ALL":
        df_dict=Tables2DF(crsrs,*tbls,LB=str(LookBackWindow))
    else: df_dict=Tables2DF(crsrs,*tbls)
    
    headers=list(df_dict.values()[0])
    
    temp1=[]
    for tbl in TableList:
        temp1=temp1+[tbl]*3
        
    temp2=[]
    for header in headers:
        temp2=temp2+[header]*3
        
    rlt_cols = [np.array(temp1), np.array(['Level', 'Z', 'PCTL']*len(TableList))]
    rlt_index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(headers))]

    return df_dict, rlt_cols, rlt_index, headers, tbls


def GetRltDF(tbls,df_dict,headers,rlt_cols,rlt_index,*ylds):
    Values=[] 
    u=UtilityClass() 
    
    for tbl in tbls:  # Compute spreads for each table
        df=df_dict[tbl].sort_index()
        lvl=[]
        z=[]
        p=[]
        for each in headers: # for each column in spread dataframe, compute zscore and percentile
            ss=df[each].to_frame()
            [s_lvl,s_zscore]=u.calc_z_score(ss,False,'1w','1m')
            s_ptl=u.calc_percentile(ss,'1w','1m')
            if ylds==():
                temp=[x*100 for x in s_lvl]
                s_lvl=temp
            lvl=lvl+s_lvl
            z=z+s_zscore
            p=p+s_ptl
        Values.append(lvl)
        Values.append(z)
        Values.append(p)
    tt=np.asarray(Values) 
    rlt = pd.DataFrame(tt, index=rlt_cols, columns =rlt_index) # Construct result dataframe  
    
    return rlt.T
    

@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def SpreadsTable(LookBackWindow,TableList,path):
    """Return Today, 1week before and 1month before's Spreads Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
        TableList: a list of tables needed
    Output: Today, 1week and 1month's spreads level,zscore(asymmetric) and percentile    
    """
    tttt=datetime.datetime.now()
    
    [df_dict, rlt_cols, rlt_index, spreads, spreadstbls]=GetTbls(TableList,LookBackWindow,'Spreads',path)
    rlt=GetRltDF(spreadstbls,df_dict,spreads,rlt_cols,rlt_index)
    
    print datetime.datetime.now()-tttt # print time needed running this function
    return rlt
 
    
@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def SpreadsRDTable(LookBackWindow,TableList,path):
    """For Spot Curves, return Spread Total Return
    For Forward Curves, return Spread Roll Down
    db_str: database file directory
    LookBackWindow: Whether to select part of the table
    TableList: a list of tables needed"""
    
    tttt=datetime.datetime.now()
    [df_dict, rlt_cols, rlt_index, spreads, spreadsRDtbls]=GetTbls(TableList,LookBackWindow,'SpreadsRD',path)
    rlt=GetRltDF(spreadsRDtbls,df_dict,spreads,rlt_cols,rlt_index)  
    print datetime.datetime.now()-tttt # print time needed running this function
    return rlt


@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def SpreadsAdjRD(LookBackWindow,TableList,path):
    """For Spot Curves, return Spread Total Return
    For Forward Curves, return Spread Roll Down
    db_str: database file directory
    LookBackWindow: Whether to select part of the table
    TableList: a list of tables needed"""
    
    tttt=datetime.datetime.now()
    [df_dict, rlt_cols, rlt_index, spreads, spreadsRDtbls]=GetTbls(TableList,LookBackWindow,'SpreadsAdjRD',path)
    rlt=GetRltDF(spreadsRDtbls,df_dict,spreads,rlt_cols,rlt_index).drop('Level',axis=1,level=1)  
    print datetime.datetime.now()-tttt # print time needed running this function
    return rlt




@xw.func
@xw.arg('TableList', np.array, ndim=2)
def ButterFlysTable(LookBackWindow,TableList,path):
    """Return Today, 1week before and 1month before's Flys Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
        TableList: a list of tables needed
    """
    tttt=datetime.datetime.now()
    [df_dict, rlt_cols, rlt_index, flys, flystbls]=GetTbls(TableList,LookBackWindow,'Flys',path)
    rlt=GetRltDF(flystbls,df_dict,flys,rlt_cols,rlt_index)      
    print datetime.datetime.now()-tttt
    return rlt


@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def FlysRDTable(LookBackWindow,TableList,path):
    """For Spot Curves, return Spread Total Return
    For Forward Curves, return Spread Roll Down
    db_str: database file directory
    LookBackWindow: Whether to select part of the table
    TableList: a list of tables needed"""
    
    tttt=datetime.datetime.now()
    [df_dict, rlt_cols, rlt_index, flys, flysRDtbls]=GetTbls(TableList,LookBackWindow,'FlysRD',path)
    rlt=GetRltDF(flysRDtbls,df_dict,flys,rlt_cols,rlt_index)      
    print datetime.datetime.now()-tttt  # print time needed running the function
    return rlt


@xw.func
@xw.arg('TableList', np.array, ndim=2)
#@xw.ret(expand='table')
def FlysAdjRD(LookBackWindow,TableList,path):
    """For Spot Curves, return Spread Total Return
    For Forward Curves, return Spread Roll Down
    db_str: database file directory
    LookBackWindow: Whether to select part of the table
    TableList: a list of tables needed"""
    
    tttt=datetime.datetime.now()
    [df_dict, rlt_cols, rlt_index, flys, flysRDtbls]=GetTbls(TableList,LookBackWindow,'FlysAdjRD',path)
    rlt=GetRltDF(flysRDtbls,df_dict,flys,rlt_cols,rlt_index).drop('Level',axis=1,level=1)  
    print datetime.datetime.now()-tttt # print time needed running this function
    return rlt


    
@xw.func
@xw.arg('TableList', np.array, ndim=2)
def AdjRollDownTable(LookBackWindow,TableList,path):
    """Return Today, 1week before and 1month before's Adj_RollDown, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
    """
    tttt=datetime.datetime.now()
    TableList=removeUni(np.delete(TableList[0], 0))
    tbls=[]
    for each in TableList:
        if each.endswith('Spot'):
            tbls.append(each+'AdjTR')
        else: tbls.append(each+'AdjRD')
    
    tempDB= 'DBQ='+str(path+'\\TempData.accdb')
    conn = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + tempDB)  #Create database connection string
    [crsr,cnxn]=Build_Access_Connect(conn)
    
    
    crsrs=[(crsr,cnxn)]
    
    if str(LookBackWindow)!="ALL":
        df_dict=Tables2DF(crsrs,*tbls,LB=str(LookBackWindow))
    else: df_dict=Tables2DF(crsrs,*tbls)
   
    tenors=list(df_dict.values()[0])
    
    temp1=[]
    for tbl in tbls:
        temp1=temp1+[tbl]*3
        
    temp2=[]
    for t in tenors:
        temp2=temp2+[t]*3
        
    rlt_cols = [np.array(temp1), np.array(['Level', 'Z', 'PCTL']*len(tbls))]
    rlt_index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(tenors))]
    
    rlt=GetRltDF(tbls,df_dict,tenors,rlt_cols,rlt_index).drop('Level',axis=1,level=1)
    print datetime.datetime.now()-tttt
    return rlt




@xw.func
@xw.arg('TableList', np.array, ndim=2)
def RollDownTable(LookBackWindow,TableList,path):
    """Return Today, 1week before and 1month before's Total Return Level, Z_score, Percentile
    Arguments:
        db_str: database file directory
        LookBackWindow: Whether to select part of the table
    """
    tttt=datetime.datetime.now()
    TableList=removeUni(np.delete(TableList[0], 0))
    tbls=[]
    for each in TableList:
        if each.endswith('Spot'):
            tbls.append(each+'TR')
        else: tbls.append(each+'RD')
    
    tempDB= 'DBQ='+str(path+'\\TempData.accdb')
    conn = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + tempDB)  #Create database connection string
    [crsr,cnxn]=Build_Access_Connect(conn)
    
    crsrs=[(crsr,cnxn)]
    
    if str(LookBackWindow)!="ALL":
        df_dict=Tables2DF(crsrs,*tbls,LB=str(LookBackWindow))
    else: df_dict=Tables2DF(crsrs,*tbls)
    
    tenors=list(df_dict.values()[0])
    
    temp1=[]
    for tbl in tbls:
        temp1=temp1+[tbl]*3
        
    temp2=[]
    for t in tenors:
        temp2=temp2+[t]*3
        
    rlt_cols = [np.array(temp1), np.array(['Level', 'Z', 'PCTL']*len(tbls))]
    rlt_index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(tenors))]
    
    rlt=GetRltDF(tbls,df_dict,tenors,rlt_cols,rlt_index)
    print datetime.datetime.now()-tttt
    return rlt
    

@xw.func
@xw.arg('TableList', np.array, ndim=2)
def YieldsLvLs(LookBackWindow,TableList,path):
    #Repair_Compact_DB(path)
    TableList=removeUni(np.delete(TableList[0], 0))
   
    YldsDB= 'DBQ='+str(path+'\\YieldsData.accdb')
    conn = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + YldsDB)  #Create database connection string
    [crsr,cnxn]=Build_Access_Connect(conn)
        
    crsrs=[(crsr,cnxn)]
    
    if str(LookBackWindow)!="ALL":
        df_dict=Tables2DF(crsrs,*TableList,LB=str(LookBackWindow))
    else: df_dict=Tables2DF(crsrs,*TableList)
    
    headers=list(df_dict.values()[0])
    
    temp1=[]
    for tbl in TableList:
        temp1=temp1+[tbl]*3
        
    temp2=[]
    for header in headers:
        temp2=temp2+[header]*3
        
    rlt_cols = [np.array(temp1), np.array(['Level', 'Z', 'PCTL']*len(TableList))]
    rlt_index = [np.array(temp2), np.array(['Today', '1W Before', '1M Before']*len(headers))]
    
    rlt=GetRltDF(TableList,df_dict,headers,rlt_cols,rlt_index,True)
    return rlt



if __name__ == "__main__":
    LB='ALL'
    #c=['KRW','SG','MY','TW','US','IN','AU','CN']
    path='C:\\users\\luoying.li\\.spyder\\Modules'

    c='KRW'
    h=['Spot','Fwd3m','Fwd6m','Fwd1y','Fwd2y','Fwd3y','Fwd4y','Fwd5y']
    tt=[]
    for e in h:
        tt.append(c+e)
    tt.insert(0,'')
    ttt=[tt]
    


    print YieldsLvLs(LB,ttt,path)
    print SpreadsTable(LB,ttt,path)
    print SpreadsRDTable(LB,ttt,path) 
    print SpreadsAdjRD(LB,ttt,path)
    print FlysAdjRD(LB,ttt,path)
    print ButterFlysTable(LB,ttt,path)
    print FlysRDTable(LB,ttt,path)
    
    '''
    a=SpreadsRDTable(LB,ttt,path)
    b=SpreadsAdjRD(LB,ttt,path)

    db_schema={}
    YldsDB= 'DBQ='+str('C:\\Users\\luoying.li\\.spyder\\Modules\\TempData_be.accdb')
    conn = ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + YldsDB)
    [crsr3,cnxn3]=Build_Access_Connect(conn) 
    YldsDB1= 'DBQ='+str('C:\\Users\\luoying.li\\.spyder\\Modules\\TempData.accdb')
    conn1= ('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; ' + YldsDB1)
    [crsr,cnxn]=Build_Access_Connect(conn1) 
    tbls = crsr3.tables(tableType='TABLE').fetchall()  
    for tbl in tbls:
        if tbl.table_name not in db_schema.keys(): 
            db_schema[tbl.table_name] = list()
        for col in crsr3.columns(table=tbl.table_name):
            db_schema[tbl.table_name].append(col[3])
           
    tblss=db_schema.keys()
    sql = "SELECT * from %s" % tblss[0]  
    crsr.execute(sql)
    print crsr.fetchone()
    cnxn.close()
    cnxn3.close()
    '''