import numpy as np
import matplotlib.pyplot as plt
import george
import ROOT as r
from scipy.interpolate import BPoly
from iminuit import Minuit
import time

R = r.TRandom(0)


def epoly2(vars,pars):
    return pars[0]*np.exp(pars[1] + pars[2]*(vars[0] - 100) + pars[3]*(vars[0] - 100)*(vars[0] - 100))


def Bern(vars,pars):
    pars_coef = []
    for i in range(len(pars)):
        pars_coef.append(pars[i])
    pars_coef = np.array(pars_coef).reshape(-1,1)
    return BPoly(pars_coef[0:-2],[pars_coef[-2][0],pars_coef[-1][0]])(vars[0])


def Gaussian(vars,pars):
    return pars[2]/(np.sqrt(2*np.pi)*pars[1])*np.exp(-0.5*((vars[0] - pars[0])/pars[1])**2)


class log_like_gp:
    def __init__(self,x,y):
        self.x = x
        self.y = y
        
    def __call__(self,Amp,length):
        kernel = Amp * george.kernels.ExpSquaredKernel(metric=length)
        gp = george.GP(kernel=kernel,solver=george.HODLRSolver)

        try:
            gp.compute(self.x,yerr=np.sqrt(self.y))
            return -gp.log_likelihood(self.y)
        except:
            return np.inf

def fit_minuit_gp(num,lnprob):
    minLLH = np.inf
    best_fit_parameters = (0,0)
    for i in range(num):
        #print(i+1)
        init0 = np.random.random()*1e2
        init1 = np.random.random()*10.
        m = Minuit(lnprob,throw_nan=False,pedantic=False,print_level=0,Amp=init0,length=init1,
                    error_Amp = 10, error_length = 0.1,
                    limit_Amp = (100,1e15), limit_length = (1,20000))
        
        m.migrad()
        if m.fval < minLLH:
            minLLH = m.fval
            best_fit_parameters = m.args
    
    print("min LL",minLLH)
    print("best fit parameters",best_fit_parameters)
    return minLLH, best_fit_parameters

class log_like_gp_sig:
    def __init__(self,x,y):
        self.x = x
        self.y = y
        
    def __call__(self,Amp,length,Sigamp,sigma,mass):
        kernel1 = Amp * george.kernels.ExpSquaredKernel(metric=length)
        kernel2 = Sigamp*george.kernels.LocalGaussianKernel(location=mass,log_width=np.exp(sigma))
        kernel = kernel1 + kernel2
        gp = george.GP(kernel=kernel,solver=george.HODLRSolver)

        try:
            gp.compute(self.x,yerr=np.sqrt(self.y))
            return -gp.log_likelihood(self.y)
        except:
            return np.inf

def fit_minuit_gp_sig(num,lnprob,Bkg_prms):
    minLLH = np.inf
    best_fit_parameters = (0,0)
    for i in range(num):
        print(i+1)
        init0 = np.random.random()*1e2
        init1 = np.random.random()*10.
        init2 = np.random.random()*10.
        init3 = np.random.random()*1.
        init4 = np.random.random()*10.
        m = Minuit(lnprob,throw_nan=False,pedantic=False,print_level=0,Amp=Bkg_prms[0],length=Bkg_prms[1],Sigamp=init2,sigma=0.7,mass=125,
                    error_Amp = 10, error_length = 0.1,error_Sigamp=np.sqrt(init2),error_sigma=0.01,error_mass=0.1,
                    limit_Amp = (100,1e15), limit_length = (1,20000),limit_Sigamp = (0,400000),limit_sigma=(0.5,4),limit_mass=(120,130),
                    fix_Amp=True,fix_length=True,fix_sigma=True,fix_mass=True)
        
        m.migrad()
        if m.fval < minLLH:
            minLLH = m.fval
            best_fit_parameters = m.args
    
    print("min LL",minLLH)
    print("best fit parameters",best_fit_parameters)
    return minLLH, best_fit_parameters



tf = r.TFile.Open("diphox_shape_withGJJJDY_WithEffCor.root")


tf.cd()
tf.ReadAll()


h_hist = tf.Get("Mgg_CP0").Clone()
binwidth = h_hist.GetBinWidth(1)
nbins = h_hist.GetNbinsX()
xmin = h_hist.GetXaxis().GetXmin()
xmax = h_hist.GetXaxis().GetXmax()
h_hist.Rebin(int(2./((xmax-xmin)/nbins)))
h_hist.Scale(10)

Bern5 = r.TF1("Bern5",Bern,xmin,xmax,8)
Bern5.SetParameters(1,0.1,0.01,0.001,0.0001,0.00001)
Bern5.SetParNames("c0","c1","c2","c3","c4","c5","xmin","xmax")
Bern5.FixParameter(6,xmin)
Bern5.FixParameter(7,xmax)
h_hist.Fit(Bern5,"SR0")
binwidth = h_hist.GetBinWidth(1)
nbins = h_hist.GetNbinsX()


xmin = h_hist.GetXaxis().GetXmin()
xmax = h_hist.GetXaxis().GetXmax()
#h_hist.Rebin(int(2./((xmax-xmin)/nbins)))
#nbins = h_hist.GetNbinsX()




Ntoys = 5
mean = 125
sigma = 2*np.sqrt(2)
Amp = 1800


signal = r.TF1("signal",Gaussian,xmin,xmax,3)
signal.SetParameters(mean,sigma,Amp)
signal.SetParNames("Mean","Sigma","Amplitude")

fit_function = r.TF1("fit_function",epoly2,xmin,xmax,4)
fit_function.SetParameters(1,1,-0.01,0)
fit_function.SetParNames("Norm","a","b","c")

h_toy = h_hist.Clone("h_toy")
h_toy.Reset()
lum = np.array([1,50,100,500,1000])
lum = np.array([1,15,30,50,70,85,100])
lum = np.array([1,10])

mass = np.zeros(h_hist.GetNbinsX())
toy = np.zeros(h_hist.GetNbinsX())
truth = np.zeros(h_hist.GetNbinsX())


"""
Here I fit the GP to a toy, to set the optimal hyperparameters
"""
"""
params = np.zeros((10,2))
chi2_fit = np.zeros(10)
minLLH = np.zeros(10)
bestminLHH = np.inf
"""


for i_bin in range(1,h_hist.GetNbinsX()+1):
    mass[i_bin-1] = h_hist.GetBinCenter(i_bin)
    toy[i_bin-1] = R.Poisson(Bern5(mass[i_bin-1]))
#lnprob = log_like_gp(mass,toy)
#minLLH, best_fit_parameters = fit_minuit_gp(100,lnprob)
#params[i][:] = fit_parameters



"""
kernel = best_fit_parameters[0]*george.kernels.ExpSquaredKernel(metric=best_fit_parameters[1])
gp = george.GP(kernel,solver=george.HODLRSolver)
gp.compute(mass,yerr=np.sqrt(toy))
y_pred = gp.predict(toy,mass)[0]

chi2 = np.sum((toy-y_pred)**2/y_pred)
chi2_fit = chi2/(len(toy)-len(gp.get_parameter_vector()))
"""
#if minLLH[i] < bestminLHH:
#    bestminLHH = minLLH[i]
#    best_fit_parameters = fit_parameters


#print("Min LLH",minLLH,"Params",np.log(best_fit_parameters[0]),np.log(best_fit_parameters[1]))


chi2_mean_gp = np.zeros(len(lum))
chi2_mean_gp_err = np.zeros(len(lum))
chi2_mean_par = np.zeros(len(lum))
chi2_mean_par_err = np.zeros(len(lum))
chi2 = np.zeros(Ntoys)
EffNdf = np.zeros(Ntoys)
EffNdf_mean = np.zeros(len(lum))
chi2_mean_noNDF = np.zeros(len(lum))
chi2_var_noNDF = np.zeros(len(lum))
chi2_fit = np.zeros(Ntoys)
h_chi2 = r.TH1D("h_chi2","Chi2 ad-hoc",100,0,20)
color = ['r','b','g','c','m','k','chartreuse']
index = 0
Error = 0

#canvas1 = r.TCanvas("canvas1","Standard Canvas",600,400)
#canvas1.SetLeftMargin(0.125)
#canvas1.SetBottomMargin(0.125)

#hs = r.THStack("hs","Chi2 ad-hoc")
plt.figure(1)
for l in lum:
    print("Luminosity: ",l)
    for i in range(Ntoys):
        for i_bin in range(1,h_hist.GetNbinsX()+1):
            mass[i_bin-1] = h_hist.GetBinCenter(i_bin)
            toy[i_bin-1] = R.Poisson(l*Bern5(mass[i_bin-1]))
            h_toy.SetBinContent(i_bin,toy[i_bin-1])
            h_toy.SetBinError(i_bin,np.sqrt(toy[i_bin-1]))

        """ad-hoc"""
        #fit_function.SetParameters(1,1,-0.01,1e-6)
        #fit_function.FixParameter(0,1)       

        #fitresults = h_toy.Fit(fit_function,"SPR0Q")
        #canvas1.Update()
        #if fitresults.Status() != 0:
        #    Error += 1

        #h_chi2.Fill(fitresults.Chi2()/fitresults.Ndf())


        """george"""
        if i%1000 == 0:
            print(i/1000.)
        
        lnprob = log_like_gp(mass,toy)
        minLLH, best_fit_parameters = fit_minuit_gp(100,lnprob)
        kernel = best_fit_parameters[0]*george.kernels.ExpSquaredKernel(metric=best_fit_parameters[1])
        #kernel = np.exp(100)*george.kernels.ExpSquaredKernel(metric=best_fit_parameters[1])
        gp = george.GP(kernel,solver=george.HODLRSolver,mean=np.median(toy))
        
        gp.compute(mass,yerr=np.sqrt(toy))
        
        mass_2d = np.atleast_2d(mass).T
        covar = gp.kernel.get_value(mass_2d)
        invcovar = np.linalg.inv(covar + toy*np.eye(len(mass)))
        covarprod = np.matmul(covar,invcovar)
        #print(covarprod)
        EffNdf[i] = covarprod.trace()


        y_pred = gp.predict(toy,mass)[0]
        print(len(toy)-len(gp.get_parameter_vector()))
        chi2[i] = np.sum((toy-y_pred)**2/y_pred)
        chi2_fit[i] = chi2[i]/(len(toy)-len(gp.get_parameter_vector()))
        print('chi2',chi2[i],'EFfNdf',covarprod.trace(),'HPndf',len(gp.get_parameter_vector()))
        

        

        #plt.clf()
        #plt.scatter(mass,toy,c='r',alpha=0.8)
        #plt.plot(mass,y_pred,'b-')
        #plt.pause(0.05)

    chi2_mean_par[index] = h_chi2.GetMean()
    chi2_mean_par_err[index] = h_chi2.GetStdDev()
    #h_chi2_l = h_chi2.Clone("h_chi2_l")
    #hs.Add(h_chi2_l)
    EffNdf_mean[index] = np.mean(EffNdf)

    h_chi2.Reset()
    plt.hist(chi2,bins=50,color=color[index],label='Lum: %.1f'%l,alpha=0.8,histtype='step')
    plt.xlabel("Chi2")
    plt.ylabel("#")
    chi2_mean_noNDF[index] = np.mean(chi2)
    chi2_var_noNDF[index] = np.var(chi2)
    chi2_mean_gp[index] = np.mean(chi2_fit)
    chi2_mean_gp_err[index] = np.std(chi2_fit)

    index += 1

#hs.Draw("plc nostack")
#canvas1.Update()
plt.legend()
plt.title("Test statistic distribution")
#plt.show()
plt.savefig('Test_statistic_distribution.png',format='png')
plt.figure(2)

plt.errorbar(lum,chi2_mean_gp,yerr=chi2_mean_gp_err,color='r', label='GP',marker='.')
plt.errorbar(lum,chi2_mean_par,yerr=chi2_mean_par_err,color='b',label='Ad-hoc',marker='.')
plt.xlabel('Luminosity scale factor')
plt.ylabel(r'$\chi^2/ndf$')
plt.legend()
plt.savefig('Lum_chi2_mean.png',format='png')

#plt.show()

print("chi2 mean: ",chi2_mean_noNDF," chi2 var: ", chi2_var_noNDF, " factor: ", chi2_var_noNDF/chi2_mean_noNDF, "EffNdf",EffNdf_mean)


""" Spurious signal testing"""
"""

Ntoys = 1
for t in range(Ntoys):
    for i_bin in range(1,h_hist.GetNbinsX()+1):
        toy[i_bin-1] = R.Poisson(10*(Bern5(mass[i_bin-1])+signal(mass[i_bin-1])))
        h_toy.SetBinContent(i_bin,toy[i_bin-1])
        h_toy.SetBinError(i_bin,np.sqrt(toy[i_bin-1]))
    mass_blind = []
    toy_blind = []
    for i in range(len(mass)):
        if mass[i] < 120 or mass[i] > 130:
            mass_blind.append(mass[i])
            toy_blind.append(toy[i])
    mass_blind = np.array(mass_blind)
    toy_blind = np.array(toy_blind)
        
    lnprob = log_like_gp(mass_blind,toy_blind)
    minLLH, best_fit_parameters = fit_minuit_gp(100,lnprob)
    kernel = best_fit_parameters[0]*george.kernels.ExpSquaredKernel(metric=best_fit_parameters[1])
    #kernel = np.exp(100)*george.kernels.ExpSquaredKernel(metric=best_fit_parameters[1])
    gp = george.GP(kernel,solver=george.HODLRSolver)
    gp.compute(mass_blind,yerr=np.sqrt(toy_blind))

    y_pred, y_var = gp.predict(toy_blind,mass,return_var=True)
    
    lnprob_sig = log_like_gp_sig(mass,toy)
    minLLH_sig,best_fit_parameters_sig = fit_minuit_gp_sig(100,lnprob_sig,best_fit_parameters)
    kernel1 = best_fit_parameters[0] * george.kernels.ExpSquaredKernel(metric=best_fit_parameters[1])
    kernel2 = best_fit_parameters_sig[2]*george.kernels.LocalGaussianKernel(location=best_fit_parameters_sig[4],log_width=best_fit_parameters_sig[3]**2)
    kernel = kernel1 + kernel2
    gp = george.GP(kernel=kernel,solver=george.HODLRSolver)
    gp.compute(mass,yerr=np.sqrt(toy))


    y_pred_sig, y_var_sig = gp.predict(toy,mass,return_var=True)

    res_pred = y_pred_sig-y_pred
    res_Std = np.sqrt(y_var + y_var_sig)

    #plt.clf()
    plt.scatter(mass,toy,c='r',alpha=0.8,marker='.')
    plt.plot(mass,y_pred,'b-')
    plt.plot(mass,y_pred_sig,'g-')
    plt.plot(mass,res_pred,'k-')
    plt.fill_between(mass,y_pred-np.sqrt(y_var),y_pred+np.sqrt(y_var),color='k',alpha=0.4)
    plt.fill_between(mass,res_pred-res_Std,res_pred+res_Std,color='k',alpha=0.4)
    #plt.pause(0.05)
    plt.show()

"""

