from scipy import interpolate
import numpy as np

class YieldCurve:
    """Build Curve with given points and Calculate roll_down with given tenor and roll_down period"""
    acceptableKeyList = ['3m', '6m', '9m', '1y', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y', '20y', '30y']
    tenorDict = {'s':0,'3m': 0.25, '6m': 0.5, '9m': 0.75, '1y': 1, '2y': 2, '3y': 3, '4y': 4, '5y': 5, '6y': 6, '7y': 7,
                 '8y': 8, '9y': 9, '10y': 10, '20y': 20, '30y': 30}

    def __init__(self, **kwargs):
        """Initialize a dictionary with given yield
        Keyword Argument:
        kwargs -- list of yield points, in form of {'1y': yield}
        """
        self.yieldDict = {}
        if kwargs is not None:
            for key in kwargs.keys():
                if key in YieldCurve.acceptableKeyList:
                    self.yieldDict[key] = kwargs[key]

    def build_curve(self, interpolate_tenor):
        """Build a cubic spline curve with given yields

        Argument:
        interpolate_tenor -- list of points in form of double number e.g [3.74,3.75] or a single tenor point   e.g 3.5

        Output: List of yields with respect to the given tenors or a single yield if there is only one tenor
        """

        tenors = []
        yields = []
        for key in self.yieldDict.keys():
            tenors.append(YieldCurve.tenorDict[key])
            yields.append(self.yieldDict[key])
        try:
            if type(interpolate_tenor) is not list:
                if interpolate_tenor<np.min(tenors):
                    raise ValueError
            else:
                for each in interpolate_tenor:
                    if each<np.min(tenors):
                        raise ValueError
            fit_curve = interpolate.interp1d(tenors, yields, kind='cubic')  # cubit spline interpolation
            #print(list(fit_curve(interpolate_tenor)))
            if type(interpolate_tenor) is not list:
                return fit_curve(interpolate_tenor)
            else:
                return list(fit_curve(interpolate_tenor))

        except (Exception) :
            print("Error: one of the interpolate tenor is too small")




    def calc_roll_down(self, tenor, roll_down, *spot):
        """Calculate roll_down with given parameters

        Arguments:
        tenor -- list of tenors compatible with acceptableKeyList eg. ['1y','3y']
        roll_down -- list of roll_down periods compatible with acceptableKeyList eg. ['3m','3m']

        Output: List of roll_down
        """
        if spot==():        
            if type(tenor) is list:
                t = [YieldCurve.tenorDict[x]for x in tenor]
                rd =[YieldCurve.tenorDict[x]for x in roll_down]
                yields1 = self.build_curve(t)
                zip_tenors = zip(t,rd)
                yields2 = self.build_curve([x-y for x,y in zip_tenors])
                zip_lists = zip(yields1, yields2)
                return [x-y for x,y in zip_lists]
            else:
                t=YieldCurve.tenorDict[tenor]
                rd=YieldCurve.tenorDict[roll_down]
                yields1=self.build_curve(t)
                yields2=self.build_curve(t-rd)
                return yields1-yields2
        else:
            if type(tenor) is list:
                t = [YieldCurve.tenorDict[x]for x in tenor]
                rd =[YieldCurve.tenorDict[x]for x in roll_down]
                s=YieldCurve(**spot[0])
                yields1=s.build_curve(t)
                yields2=self.build_curve(t)
                n=[YieldCurve.tenorDict[spot[1]]/x for x in rd]
                return [(x-y)/z for x,y,z in zip(yields2,yields1,n)]
            else:
                t=YieldCurve.tenorDict[tenor]
                rd=YieldCurve.tenorDict[roll_down]
                s=YieldCurve(**spot[0])
                yields1=s.build_curve(t)
                yields2=self.build_curve(t)
                n=YieldCurve.tenorDict[spot[1]]/rd
                return (yields2-yields1)/n
            

    
    def calc_FRA(self,t1,t2,*DayCount,**kwargs):
        """Calculate FRA between t1 and t2
        Argument:
            t1    -- e.g '3m'
            t2    -- e.g '1y'  Contract period is then t2-t1.
            Daycount  -- two choices: 360 or 365. Exist together with **kwargs
            **kwargs  -- key word arguments. Required key words: n1 and n2
                         e.g  n1=91, n1 refers to the actual days in period tenor1
                              n2=183, n2 refers to the actual days in period tenor2
        Output:
            Annulised FRA rate bwteen t1 and t2
        """
        t1=YieldCurve.tenorDict[t1]  # change string to number
        t2=YieldCurve.tenorDict[t2]  # change string to number
        rates=self.build_curve([t1,t2])  # get interpolated rate for t1,t2
        #print t1, t2, rates
        
        if kwargs=={}:
            return ((1+rates[1]*t2)/(1+rates[0]*t1)-1)/(t2-t1) # if no actual days, set as 90/360 convention
        else: # else, go with actual date count convention
            n1=kwargs['n1']
            n2=kwargs['n2']
            nf=n2-n1
            return (rates[1]*n2-rates[0]*n1)/nf/(1+rates[0]*n1/DayCount[0])
        
'''     
if __name__ == "__main__":
    kwargs = {'1y': np.log(1), '2y': np.log(2), '4y': np.log(4),'6y': np.log(6),
              '7y': np.log(7), '9y': np.log(9), '10y': np.log(10)}
    yy = YieldCurve(**kwargs)
    print yy.build_curve(3)
    print yy.calc_FRA('3y','5y')
    print yy.calc_FRA('3y','5y',360)
    print yy.calc_FRA('3y','5y',365,n1=730,n2=1461)
''' 
    
    


