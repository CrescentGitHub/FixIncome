from YieldCurve import YieldCurve
import numpy as np

class SpotCurve:

    def __init__(self, spot_r, forward_r):
        self.spot_curve = YieldCurve(**spot_r)
        self.forward_curve = YieldCurve(**forward_r)

    def calc_roll_down(self, tenor, roll_down_period,*spot):
        """Calculate roll_down with given parameters

        Arguments:
        tenor -- list of tenors compatible with acceptableKeyList eg. ['1y','3y']
        roll_down -- list of roll_down periods compatible with acceptableKeyList eg. ['3m','3m']

        Output: List of roll_down
        """
        return self.spot_curve.calc_roll_down(tenor,roll_down_period,*spot)

    def calc_total_return(self, tenor, total_return_period):
        """Calculate total return of given period at given tenor

        Arguments
        tenor -- list of tenors e.g ['5y','6y']
        total_return_period -- list of periods e.g ['3m','3m']

        Output: list of total return
        """
        if type(tenor) is list:
            t = [YieldCurve.tenorDict[x] for x in tenor]
            prd = [YieldCurve.tenorDict[x] for x in total_return_period]
            zip_tenors = zip(t, prd)
            temp_t=[x - y for x, y in zip_tenors]
            yields1 = self.forward_curve.build_curve(temp_t)
            yields2 = self.spot_curve.build_curve(temp_t)
            zip_lists = zip(yields1, yields2)
            return [x - y for x, y in zip_lists]
        else:
            t=YieldCurve.tenorDict[tenor]
            prd=YieldCurve.tenorDict[total_return_period]
            return self.forward_curve.build_curve(t-prd)-self.spot_curve.build_curve(t-prd)

    def calc_carry(self, tenor, carry_period):
        """calculate carry of given tenor and carry_period

        Arguments
        tenor -- list of tenors e.g ['5y','6y']
        carry_period -- list of periods e.g ['3m','3m']

        Output: List of carry
        """
        if type(tenor) is list:
            t = [YieldCurve.tenorDict[x] for x in tenor]
            prd = [YieldCurve.tenorDict[x] for x in carry_period]
            zip_tenors = zip(t, prd)
            yields1 = self.forward_curve.build_curve([x - y for x, y in zip_tenors])
            yields2 = self.spot_curve.build_curve(t)
            zip_lists = zip(yields1, yields2)
            return [x - y for x, y in zip_lists]
        else:
            t=YieldCurve.tenorDict[tenor]
            prd=YieldCurve.tenorDict[carry_period]
            return self.forward_curve.build_curve(t-prd)-self.spot_curve.build_curve(t)



