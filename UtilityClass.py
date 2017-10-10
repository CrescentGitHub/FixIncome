import numpy as np
from scipy import stats
import pandas as pd
import datetime 


class UtilityClass:
    """Calculate Z_score of a given time series"""
    
    @staticmethod
    def z_score(series_list,symmetric):
        mu = np.mean(series_list)
        sigma = np.std(series_list)
        if symmetric:
            
            return (series_list[-1]-mu)/sigma
        # if the series is not symmetric, compute two different sigma
        else:
            #print series_list[-1][0]
            below_aver = list(filter(lambda x: x < mu, series_list))
            above_aver = list(filter(lambda x: x > mu, series_list))
            sigma_neg = np.std(below_aver)
            sigma_pos = np.std(above_aver)
            if series_list[-1]>mu:
                return (series_list[-1]-mu)/sigma_pos
            else:
                return (series_list[-1]-mu)/sigma_neg
    
    @staticmethod
    def calc_z_score(df, symmetric, *choice):
        """Calculate Z_score

        Arguments:
        df -- a dataframe to be analysed
        symmetric -- a boolean variable indicating whether the series is symmetric
        
        """
        
        
        series_list=df[df.columns[0]].values
        idx=df.index.tolist()
        idx_now=idx[-1]
        zscore=UtilityClass.z_score(series_list,symmetric)
        lvl=series_list[-1]
        if choice != ():
            zscore=[zscore]
            lvl=[lvl]
            for each in choice:
                if each=='1d':
                    while True:
                        lastD=idx_now-datetime.timedelta(days=1)
                        if lastD in idx:
                            break
                    df1=df.loc[: lastD]
                    series_list=df1[df1.columns[0]].values
                    #print series_list
                    lvl.append(series_list[-1])
                    zscore.append(UtilityClass.z_score(series_list,symmetric))
                if each=='1w':
                    lastW=idx_now-datetime.timedelta(weeks=1)
                    while lastW not in idx:
                        lastW=lastW-datetime.timedelta(days=1)
                    df1=df.loc[: lastW]
                    series_list=df1[df1.columns[0]].values
                    lvl.append(series_list[-1])
                    zscore.append(UtilityClass.z_score(series_list,symmetric))
                if each=='1m':
                    lastM=idx_now-datetime.timedelta(days=30)
                    while lastM not in idx:
                        lastM=lastM-datetime.timedelta(days=1)
                    df1=df.loc[: lastM]
                    series_list=df1[df1.columns[0]].values
                    lvl.append(series_list[-1])
                    zscore.append(UtilityClass.z_score(series_list,symmetric))
        #print zscore
        return lvl, zscore        
                                               

    @staticmethod
    def calc_percentile(df, *choice):
        """return the percentile of the last point in the list

        Argument:
        series_list -- list of returns to be analysed
        """
        pctl=[]
        series_list=df[df.columns[0]].values
        #print series_list
        idx=df.index.tolist()
        idx_now=idx[-1]
        #print series_list[-1]
        pctl=stats.percentileofscore(series_list,series_list[-1],kind='weak')/100
        
        if choice != ():
            pctl=[pctl]
            for each in choice:
                if each=='1d':
                    while True:
                        lastD=idx_now-datetime.timedelta(days=1)
                        if lastD in idx:
                            break
                    df1=df.loc[: lastD]
                    series_list=df1[df1.columns[0]].values
                    pctl.append(stats.percentileofscore(series_list,series_list[-1],kind='weak')/100)
                if each=='1w':
                    lastW=idx_now-datetime.timedelta(weeks=1)
                    while lastW not in idx:
                        lastW=lastW-datetime.timedelta(days=1)
                    df1=df.loc[: lastW]
                    series_list=df1[df1.columns[0]].values
                    pctl.append(stats.percentileofscore(series_list,series_list[-1],kind='weak')/100)
                if each=='1m':
                    lastM=idx_now-datetime.timedelta(days=30)
                    while lastM not in idx:
                        lastM=lastM-datetime.timedelta(days=1)
                    df1=df.loc[: lastM]
                    series_list=df1[df1.columns[0]].values
                    pctl.append(stats.percentileofscore(series_list,series_list[-1],kind='weak')/100)      
        return pctl


    @staticmethod
    def calc_percentile_level(df, perctl, *choice):
        """return the percentile level of a given list

        Argument:
        series_list -- list of returns to be analysed
        perctl -- target percentile e.g 25 means the method returns a value of 25% percentile of the list
        """
     
        series_list=df.values.tolist()
        idx=df.index.tolist()
        idx_now=idx[-1]
        lvl=np.percentile(series_list, perctl)
        
        if choice != ():
            lvl=[lvl]
            for each in choice:
                if each=='1d':
                    while True:
                        lastD=idx_now-datetime.timedelta(days=1)
                        if lastD in idx:
                            break
                    df1=df.loc[: lastD]
                    series_list=df1.values.tolist()
                    lvl.append(np.percentile(series_list, perctl))
                if each=='1w':
                    lastW=idx_now-datetime.timedelta(weeks=1)
                    while lastW not in idx:
                        lastW=lastW-datetime.timedelta(days=1)
                    df1=df.loc[: lastW]
                    series_list=df1.values.tolist()
                    lvl.append(np.percentile(series_list, perctl))
                if each=='1m':
                    lastM=idx_now-datetime.timedelta(days=30)
                    while lastM not in idx:
                        lastM=lastM-datetime.timedelta(days=1)
                    df1=df.loc[: lastM]
                    series_list=df1.values.tolist()
                    lvl.append(np.percentile(series_list, perctl))      
        return lvl
        
'''

if __name__ == "__main__":
    today=datetime.date.today()
    dates=[]
    for i in range(100):
        dd=today-datetime.timedelta(days=1+i)
        dates.insert(0,dd)
    
    s = pd.DataFrame(range(100), index=dates)
    u=UtilityClass()
    Result=[]
    Result.append(u.calc_z_score(s,True))
    Result.append( u.calc_z_score(s,True,'1d','1w'))
    Result.append( u.calc_z_score(s,False))
    Result.append( u.calc_z_score(s,False,'1d','1w'))
    Result.append( u.calc_percentile(s))
    Result.append( u.calc_percentile(s,'1d','1w'))
    Result.append( u.calc_percentile_level(s,95))
    Result.append( u.calc_percentile_level(s,95,'1d','1w'))
    print Result
'''