# -*- coding: utf-8 -*-
"""
Contains many different periodogram calculations

The basic interface is

>>> freq,ampl = scargle(times,signal)

If you give no extra information, default values for the start, end and step
frequency will be chosen. See the 'defaults_pergram' decorator for a list of
keywords common to all periodogram calculations.

All periodograms can be computed in parallel, by supplying an extra keyword
'threads':

>>> freq,ampl = scargle(times,signal,threads=2)

"""
import numpy as np
from numpy import cos,sin,pi
from ivs.misc.decorators import make_parallel
from ivs.timeseries.decorators import parallel_pergram,defaults_pergram

import pyscargle
import pyclean
import pyGLS
import pyKEP
import multih
import deeming as fdeeming
import eebls


def windowfunction(time, freq):

    """
    Computes the modulus square of the window function of a set of 
    time points at the given frequencies. The time point need not be 
    equidistant. The normalisation is such that 1.0 is returned at 
    frequency 0.
    
    @param time: time points  [0..Ntime-1]
    @type time: ndarray       
    @param freq: frequency points. Units: inverse unit of 'time' [0..Nfreq-1]
    @type freq: ndarray       
    @return: |W(freq)|^2      [0..Nfreq-1]
    @rtype: ndarray
    
    """
  
    Ntime = len(time)
    Nfreq = len(freq)
    winkernel = np.empty_like(freq)

    for i in range(Nfreq):
        winkernel[i] = np.sum(np.cos(2.0*pi*freq[i]*time))**2     \
                     + np.sum(np.sin(2.0*pi*freq[i]*time))**2

    # Normalise such that winkernel(nu = 0.0) = 1.0 

    return winkernel/Ntime**2



@defaults_pergram
@parallel_pergram
@make_parallel
def scargle(times, signal, f0=None, fn=None, df=None, norm='amplitude', weights=None):
    """
    Scargle periodogram of Scargle (1982).
    
    Several options are available (possibly combined):
        1. weighted Scargle
        2. Amplitude spectrum
        3. Distribution power spectrum
        4. Traditional power spectrum
        5. Power density spectrum (see Kjeldsen, 2005 or Carrier, 2010)
    
    This definition makes use of a Fortran-routine written by Jan Cuypers, Conny
    Aerts and Peter De Cat. A slightly adapted version is used for the weighted
    version (adapted by Pieter Degroote).
    
    Through the option "norm", it's possible to norm the periodogram as to get a
    periodogram that has a known statistical distribution. Usually, this norm is
    the variance of the data (NOT of the noise or residuals!).
    
    Also, it is possible to retrieve the power density spectrum in units of
    [ampl**2/frequency]. In this routine, the normalisation constant is taken
    to be the total time span T. Kjeldsen (2005) chooses to multiply the power
    by the 'effective length of the observing run', which is calculated as the
    reciprocal of the area under spectral window (in power, and take 2*Nyquist
    as upper frequency value).
    
    REMARK: this routine does B{not} automatically remove the average. It is the
    user's responsibility to do this adequately: e.g. subtract a B{weighted}
    average if one computes the weighted periodogram!!
    
    @param times: time points
    @type times: numpy array
    @param signal: observations
    @type signal: numpy array
    @param weights: weights of the datapoints
    @type weights: numpy array
    @param norm: type of normalisation
    @type norm: str
    @param f0: start frequency
    @type f0: float
    @param fn: stop frequency
    @type fn: float
    @param df: step frequency
    @type df: float
    @return: frequencies, amplitude spectrum
    @rtype: array,array
    """ 
    #-- initialize variables for use in Fortran routine
    sigma=0.;xgem=0.;xvar=0.;n=len(times)
    T = times.ptp()
    nf=int((fn-f0)/df+0.001)+1
    f1=np.zeros(nf,'d');s1=np.zeros(nf,'d')
    ss=np.zeros(nf,'d');sc=np.zeros(nf,'d');ss2=np.zeros(nf,'d');sc2=np.zeros(nf,'d')
    
    #-- run the Fortran routine
    if weights is None:
        f1,s1=pyscargle.scar2(signal,times,f0,df,f1,s1,ss,sc,ss2,sc2)
    else:
        w=np.array(weights,'float')
        logger.debug('Weighed scargle')
        f1,s1=pyscargle.scar3(signal,times,f0,df,f1,s1,ss,sc,ss2,sc2,w)
    
    #-- search for peaks/frequencies/amplitudes    
    if not s1[0]: s1[0]=0. # it is possible that the first amplitude is a none-variable
    fact  = np.sqrt(4./n)
    if norm =='distribution': # statistical distribution
        s1 /= np.var(signal)
    elif norm == "amplitude": # amplitude spectrum
        s1 = fact * np.sqrt(s1)
    elif norm == "density": # power density
        s1 = fact**2 * s1 * T
        
    return f1, s1











@defaults_pergram
@parallel_pergram
@make_parallel
def deeming(times,signal, f0=None, fn=None, df=None, norm='amplitude'):
    """
    Deeming periodogram of Deeming et al. (1975).
    
    Thanks to Jan Cuypers
    
    @param times: time points
    @type times: numpy array
    @param signal: observations
    @type signal: numpy array
    @param norm: type of normalisation
    @type norm: str
    @param f0: start frequency
    @type f0: float
    @param fn: stop frequency
    @type fn: float
    @param df: step frequency
    @type df: float
    @return: frequencies, amplitude spectrum
    @rtype: array,array
    """        
    #-- initialize variables for use in Fortran routine
    nf=int((fn-f0)/df+0.001)+1
    n = len(times)
    T = times.ptp()
    f1,s1 = fdeeming.deeming1(times,signal,f0,df,nf)
    s1 /= n
    fact  = np.sqrt(4./n)
    fact  = np.sqrt(4./n)
    if norm =='distribution': # statistical distribution
        s1 /= np.var(signal)
    elif norm == "amplitude": # amplitude spectrum
        s1 = fact * np.sqrt(s1)
    elif norm == "density": # power density
        s1 = fact**2 * s1 * T
    
    return f1,s1
    
    
    
    
    
def DFTpower(time, signal, f0=None, fn=None, df=None):

    """
    Computes the modulus square of the fourier transform. 
    Unit: square of the unit of signal. Time points need not be equidistant.
    The normalisation is such that a signal A*sin(2*pi*nu_0*t)
    gives power A^2 at nu=nu_0
    
    @param time: time points [0..Ntime-1] 
    @type time: ndarray
    @param signal: signal [0..Ntime-1]
    @type signal: ndarray
    @param f0: the power is computed for the frequencies
                      freq = arange(startfreq,stopfreq,stepfreq)
    @type f0: float
    @param fn: see startfreq
    @type fn: float
    @param df: see startfreq
    @type df: float
    @return: power spectrum of the signal
    @rtype: ndarray 
    """
  
    Ntime = len(time)
    Nfreq = int(np.ceil((stopfreq-startfreq)/stepfreq))
  
    A = np.exp(1j*2.*pi*startfreq*time) * signal
    B = np.exp(1j*2.*pi*stepfreq*time)
    ft = np.zeros(Nfreq, complex) 
    ft[0] = A.sum()

    for k in range(1,Nfreq):
        A *= B
        ft[k] = np.sum(A)
    
    return (ft.real**2 + ft.imag**2) * 4.0 / Ntime**2    
    
    
    
def FFTpower(signal, timestep):

    """
    Computes power spectrum of an equidistant time series 'signal'
    using the FFT algorithm. The length of the time series need not
    be a power of 2 (zero padding is done automatically). 
    Normalisation is such that a signal A*sin(2*pi*nu_0*t)
    gives power A^2 at nu=nu_0  (IF nu_0 is in the 'freq' array)
    
    @param signal: the time series [0..Ntime-1]
    @type signal: ndarray
    @param timestep: time step fo the equidistant time series
    @type timestep: float
    @return: frequencies and the power spectrum
    @rtype: (ndarray,ndarray)
    
    """
  
    # Compute the FFT of a real-valued signal. If N is the number 
    # of points of the original signal, 'Nfreq' is (N/2+1).
  
    fourier = np.fft.rfft(signal)
    Ntime = len(signal)
    Nfreq = len(fourier)
  
    # Compute the power
  
    power = np.abs(fourier)**2 * 4.0 / Ntime**2
  
    # Compute the frequency array.
    # First compute an equidistant array that goes from 0 to 1 (included),
    # with in total as many points as in the 'fourier' array.
    # Then rescale the array that it goes from 0 to the Nyquist frequency
    # which is 0.5/timestep
  
    freq = np.arange(float(Nfreq)) / (Nfreq-1) * 0.5 / timestep
  
    # That's it!
  
    return (freq, power)





  
  
  
def FFTpowerdensity(signal, timestep):
  
    """
    Computes the power density of an equidistant time series 'signal',
    using the FFT algorithm. The length of the time series need not
    be a power of 2 (zero padding is done automatically). 

    @param signal: the time series [0..Ntime-1]
    @type signal: ndarray
    @param timestep: time step fo the equidistant time series
    @type timestep: float
    @return: frequencies and the power density spectrum
    @rtype: (ndarray,ndarray)

    """
  
    # Compute the FFT of a real-valued signal. If N is the number 
    # of points of the original signal, 'Nfreq' is (N/2+1).
  
    fourier = np.fft.rfft(signal)
    Ntime = len(signal)
    Nfreq = len(fourier)
  
    # Compute the power density
  
    powerdensity = np.abs(fourier)**2 / Ntime * timestep
  
    # Compute the frequency array.
    # First compute an equidistant array that goes from 0 to 1 (included),
    # with in total as many points as in the 'fourier' array.
    # Then rescale the array that it goes from 0 to the Nyquist frequency
    # which is 0.5/timestep
  
    freq = np.arange(float(Nfreq)) / (Nfreq-1) * 0.5 / timestep
  
    # That's it!
  
    return (freq, powerdensity)

  


  
  



def weightedpower(time, signal, weight, freq):

    """
    Compute the weighted power spectrum of a time signal.
    For each given frequency a weighted sine fit is done using
    chi-square minimization.
    
    @param time: time points [0..Ntime-1] 
    @type time: ndarray
    @param signal: observations [0..Ntime-1]
    @type signal: ndarray
    @param weight: 1/sigma_i^2 of observation
    @type weight: ndarray
    @param freq: frequencies [0..Nfreq-1] for which the power 
                 needs to be computed
    @type freq: ndarray
    @return: weighted power [0..Nfreq-1]
    @rtype: ndarray
    
    """

    result = np.zeros(len(freq))

    for i in range(len(freq)):
        if (freq[i] != 0.0):
            sine   = np.sin(2.0*pi*freq[i]*time)
            cosine = np.cos(2.0*pi*freq[i]*time)
            a11= np.sum(weight*sine*sine)
            a12 = np.sum(weight*sine*cosine)
            a21 = a12
            a22 = np.sum(weight*cosine*cosine)
            b1 = np.sum(weight*signal*sine)
            b2 = np.sum(weight*signal*cosine)
            denominator = a11*a22-a12*a21
            A = (b1*a22-b2*a12)/denominator
            B = (b2*a11-b1*a21)/denominator
            result[i] = A*A+B*B
        else:
            result[i] = np.sum(signal)/len(signal)

    return(result)    
    
    
    
    
@defaults_pergram
@parallel_pergram
@make_parallel
def gls(times,signal, f0=None, fn=None, df=None, errors=None, wexp=2):
    """
    Generalised Least Squares periodogram of Zucher et al. (2010).
    
    @param times: time points
    @type times: numpy array
    @param signal: observations
    @type signal: numpy array
    @param f0: start frequency
    @type f0: float
    @param fn: stop frequency
    @type fn: float
    @param df: step frequency
    @type df: float
    @return: frequencies, amplitude spectrum
    @rtype: array,array
    """
    T = times.ptp()
    n = len(times)
    if errors is None:
        errors = np.ones(n)
    maxstep = int((fn-f0)/df+1)
    
    #-- initialize parameters
    f1 = np.zeros(maxstep) #-- frequency
    s1 = np.zeros(maxstep) #-- power
    p1 = np.zeros(maxstep) #-- window
    l1 = np.zeros(maxstep) #-- power LS
    
    #-- calculate generalized least squares
    pyGLS.gls(times+0.,signal+0.,errors,f0,fn,df,wexp,f1,s1,p1,l1)
    
    return f1,s1











@defaults_pergram
@parallel_pergram
@make_parallel
def clean(times,signal, f0=None, fn=None, df=None, freqbins=None, niter=10.,
          gain=1.0):
    """
    Cleaned Fourier periodogram of Roberts et al. (1987)
        
    Parallization probably isn't such a good idea here because of the frequency
    bins.
    
    Fortran module probably from John Telting.
    
    Should always start from zero, so f0 is not an option
        >>> times_ = np.linspace(0,150,1000)
        >>> times = np.array([times_[i] for i in xrange(len(times_)) if (i%10)>7])
        >>> signal = np.sin(2*pi/10*times) + np.random.normal(size=len(times))
        >>> niter,freqbins = 10,[0,1.2]
        >>> p1 = scargle(times,signal,fn=1.2,norm='amplitude',threads=2)
        >>> p2 = clean(times,signal,fn=1.2,gain=1.0,niter=niter,freqbins=freqbins)
        >>> p3 = clean(times,signal,fn=1.2,gain=0.1,niter=niter,freqbins=freqbins)
        >>> from pylab import figure,plot,legend
        >>> p=figure()
        >>> p=plot(p1[0],p1[1],'k-',label="Scargle")
        >>> p=plot(p2[0],p2[1],'r-',label="Clean (g=1.0)")
        >>> p=plot(p3[0],p3[1],'b-',label="Clean (g=0.1)")
        >>> p=legend()
    
    @keyword freqbins: frequency bins for clean computation
    @type freqbins: list or array
    @keyword niter: number of iterations
    @type niter: integer
    @keyword gain: gain for clean computation
    @type gain: float between 0 (no cleaning) and 1 (full cleaning)
    @return: frequencies, amplitude spectrum
    @rtype: array,array
    """
    T = times.ptp()
    n = len(times)
    if freqbins is None:
        freqbins = [f0,fn]
    
    startfreqs = np.array(freqbins[0::2])
    endfreqs = np.array(freqbins[1::2])
    nbins = len(freqbins)-1
    
    nf = int(fn/df)
    
    #-- do clean computation, seems not so straightforward to thread cleaning
    f,wpow,wpha = pyclean.main_clean(times,signal,fn,nf,gain,niter,nbins,\
                    startfreqs,endfreqs)
    
    return f,wpow









@defaults_pergram
@parallel_pergram
@make_parallel
def schwarzenberg_czerny(times, signal, f0=None, fn=None, df=None, nh=2, mode=1):
    """
    Multi harmonic periodogram of Schwarzenberg-Czerny (1996).
    
    This periodogram follows an F-distribution, so it is possible to perform
    hypothesis testing.
    
    If the number of the number of harmonics is 1, then this peridogram reduces
    to the Lomb-Scargle periodogram except for its better statistic behaviour.
    This script uses a Fortran procedure written by Schwarzenberg-Czerny.
    
    @param times: list of observations times
    @type times: numpy 1d array
    @param signal: list of observations
    @type signal: numpy 1d array
    @keyword f0: start frequency (cycles per day) (default: 0.)
    @type f0: float
    @keyword fn: stop frequency (cycles per day) (default: 10.)
    @type fn: float
    @keyword df: step frequency (cycles per day) (default: 0.001)
    @type df: float
    @keyword nh: number of harmonics to take into account
    @type nh: integer
    @return: frequencies, f-statistic
    @rtype: array,array
    """
    T = times.ptp()
    n = len(times)
    frequencies = np.arange(f0, fn+df, df)
    ll   = len(frequencies)
    th   = np.zeros(len(frequencies))
    #-- use Fortran subroutine
    th  = multih.sfou(n,times,signal,ll,f0,df,nh,mode,th)
    
    # th *= 0.5 seemed necessary to fit the F-distribution
        
    return frequencies,th









@defaults_pergram
@parallel_pergram
@make_parallel
def pdm(times, signal, f0=None, fn=None, df=None, Nbin=5, Ncover=2, D=0):
    """
    Phase Dispersion Minimization of Jurkevich-Stellingwerf (1978)
    
    This definition makes use of a Fortran routine written by Jan Cuypers and
    Conny Aerts.
    
    Inclusion of linear frequency shift by Pieter Degroote (see Cuypers 1986)
    
    @param times: time points
    @type times: numpy array
    @param signal: observations
    @type signal: numpy array
    @param f0: start frequency
    @type f0: float
    @param fn: stop frequency
    @type fn: float
    @param df: step frequency
    @type df: float
    @param Nbin: number of bins (default: 5)
    @type Nbin: int
    @param Ncover: number of covers (default: 1)
    @type Ncover: int
    @param D: linear frequency shift parameter
    @type D: float
    @return: frequencies, theta statistic
    @rtype: array,array
    """
    T = times.ptp()
    n  = len(times)
    
    #-- initialize variables
    xvar     = signal.std()**2.
    xx = (n-1) * xvar
    nf = int((fn-f0) / df + 0.001) + 1
    f1 = np.zeros(nf,'d')
    s1 = np.zeros(nf,'d')
    
    #-- use Fortran subroutine
    if D is None:
        f1, s1 = pyscargle.justel(signal,times,f0,df,Nbin,Ncover,xvar,xx,f1,s1,n,nf)
    else:
        f1, s1 = pyscargle.justel2(signal,times,f0,df,Nbin,Ncover,xvar,xx,D,f1,s1,n,nf)
    
    #-- it is possible that the first computed value is a none-variable
    if not s1[0]: s1[0] = 1. 
    
    return f1, s1





@defaults_pergram
@parallel_pergram
@make_parallel
def pdm_py(time, signal, f0=None, fn=None, df=None, Nbin=10, Ncover=5, D=0.):

    """
    Computes the theta-statistics to do a Phase Dispersion Minimisation.
    See Stellingwerf R.F., 1978, ApJ, 224, 953)
    
    Joris De Ridder
    
    Inclusion of linear frequency shift by Pieter Degroote (see Cuypers 1986)
    
    @param time: time points  [0..Ntime-1]
    @type time: ndarray       
    @param signal: observed data points [0..Ntime-1]
    @type signal: ndarray
    @param f0: start frequency
    @type f0: float
    @param fn: stop frequency
    @type fn: float
    @param df: step frequency
    @type df: float
    @param Nbin: the number of phase bins (with length 1/Nbin)
    @type Nbin: integer
    @param Ncover: the number of covers (i.e. bin shifts)
    @type Ncover: integer
    @param D: linear frequency shift parameter
    @type D: float
    @return: theta-statistic for each given frequency [0..Nfreq-1]
    @rtype: ndarray
    """
    freq = np.arange(f0,fn+df,df)
    
    Ntime = len(time)
    Nfreq = len(freq)
  
    binsize = 1.0 / Nbin
    covershift = 1.0 / (Nbin * Ncover)
  
    theta = np.zeros(Nfreq)
  
    for i in range(Nfreq):
  
        # Compute the phases in [0,1[ for all time points
        phase = np.fmod((time - time[0]) * freq[i] + D/2.*time**2, 1.0)
    
        # Reset the number of (shifted) bins without datapoints
    
        Nempty = 0
    
        # Loop over all Nbin * Ncover (shifted) bins
    
        for k in range(Nbin):
            for n in range(Ncover):
        
                # Determine the left and right boundary of one such bin
                # Note that due to the modulo, right may be < left. So instead
                # of 0-----+++++------1, the bin might be 0++-----------+++1 .
        
                left = np.fmod(k * binsize + n * covershift, 1.0) 
                right = np.fmod((k+1) * binsize + n * covershift, 1.0) 

                # Select all data points in that bin
        
                if (left < right):
                    bindata = np.compress((left <= phase) & (phase < right), signal)
                else:
                    bindata = np.compress(~((right <= phase) & (phase < left)), signal)

                # Compute the contribution of that bin to the theta-statistics  
          
                if (len(bindata) != 0):
                    theta[i] += (len(bindata) - 1) * bindata.var()
                else:
                    Nempty += 1
  
        # Normalize the theta-statistics        

        theta[i] /= Ncover * Ntime - (Ncover * Nbin - Nempty)     
    
    # Normalize the theta-statistics again
  
    theta /= signal.var()  
    
    # That's it!
 
    return freq,theta











@defaults_pergram
@parallel_pergram
@make_parallel
def bls(times, signal, f0=None, fn=None, df=None, nb=50, qmi=0.005, qma=0.75 ):
    """
    Box-Least-Squares spectrum of Kovacs et al. (2002).

    [ see Kovacs, Zucker & Mazeh 2002, A&A, Vol. 391, 369 ]

    This is the slightly modified version of the original BLS routine 
    by considering Edge Effect (EE) as suggested by 
    Peter R. McCullough [ pmcc@stsci.edu ].

    This modification was motivated by considering the cases when 
    the low state (the transit event) happened to be devided between 
    the first and last bins. In these rare cases the original BLS 
    yields lower detection efficiency because of the lower number of 
    data points in the bin(s) covering the low state.

    For further comments/tests see  www.konkoly.hu/staff/kovacs.html
    
    Transit fraction and precision are given by nb,qmi and qma
    
    Remark: output parameter parameter contains:
    [frequency,depth,transit fraction width,fractional start, fraction end]
    
    @param times: observation times
    @type times: numpy 1D array
    @param signal: observations
    @type signal: numpy 1D array
    @param f0: start frequency
    @type f0: float
    @param fn: end frequency
    @type fn: float
    @param df: frequency step
    @type df: float
    @param nb: number of bins in the folded time series at any test period
    @type nb: integer
    @param qmi: minimum fractional transit length to be tested
    @type qmi: 0<float<qma<1
    @param qma: maximum fractional transit length to be tested
    @type qma: 0<qmi<float<1
    @return: frequencies, amplitude spectrum
    @rtype: array,array
    """
    
    #-- initialize some variables needed in the FORTRAN module
    n = len(times)
    T = times.ptp()
    u = np.zeros(n)
    v = np.zeros(n)
    
    #-- frequency vector and variables
    nf = (fn-f0)/df
    if f0<2./T: f0=2./T
    
    #-- calculate EEBLS spectrum and model parameters
    power,depth,qtran,in1,in2 = eebls.eebls(times,signal,u,v,nf,f0,df,nb,qmi,qma,n)
    frequencies = np.linspace(f0,fn,nf)
    
    #-- to return parameters of fit, do this:
    # pars = [max_freq,depth,qtran+(1./float(nb)),(in1-1)/float(nb),in2/float(nb)]
    return frequencies,power





@defaults_pergram
@parallel_pergram
@make_parallel
def kepler(times,signal, f0=None, fn=None, df=None, e0=0., en=0.91, de=0.1,
           errors=None, wexp=2, x00=0.,x0n=359.9):
    """
    Keplerian periodogram of Zucker et al. (2010).
    
    @param times: observation times
    @type times: numpy 1D array
    @param signal: observations
    @type signal: numpy 1D array
    @param f0: start frequency
    @type f0: float
    @param fn: end frequency
    @type fn: float
    @param df: frequency step
    @type df: float
    @param e0: start eccentricity
    @type e0: float
    @param en: end eccentricity
    @type en: float
    @param de: eccentricity step
    @type de: float
    @param x00: start x0
    @type x00: float
    @param x0n: end x0
    @type x0n: float
    @return: frequencies, amplitude spectrum
    @rtype: array,array
    """
    T = times.ptp()
    n = len(times)
    if errors is None:
        errors = np.ones(n)
    maxstep = int((fn-f0)/df+1)
    
    #-- initialize parameters
    f1 = np.zeros(maxstep) #-- frequency
    s1 = np.zeros(maxstep) #-- power
    p1 = np.zeros(maxstep) #-- window
    l1 = np.zeros(maxstep) #-- power LS
    s2 = np.zeros(maxstep) #-- power Kepler
    k2 = np.zeros(6) #-- parameters for Kepler orbit
    
    #-- calculate Kepler periodogram
    pyKEP.kepler(times+0,signal+0,errors,f0,fn,df,wexp,e0,en,de,\
          x00,x0n,f1,s1,p1,l1,s2,k2)
    return f1,s2




if __name__=="__main__":
    import pylab as pl
    from ivs.misc import loggers
    logger = loggers.get_basic_logger()
    
    x = np.linspace(0,100,100)
    y = np.sin(2*np.pi/10.*x) + np.random.normal(size=len(x),scale=0.2)
    for i,norm in enumerate(['power','amplitude','distribution','density']):
        f1,s1 = scargle(x,y,norm=norm)
        f2,s2 = deeming(x,y,norm=norm)
        pl.subplot(2,2,i+1)
        pl.plot(f1,s1,lw=2)
        pl.plot(f2,s2)
    
    pl.figure()
    f1,s1 = gls(x,y)
    f2,s2 = clean(x,y)
    f3,s3 = schwarzenberg_czerny(x,y,nh=2)
    f4,s4 = pdm(x,y)
    f5,s5 = bls(x,y)
    f6,s6 = kepler(x,y)
    
    pl.subplot(2,3,1)
    pl.plot(f1,s1)
    pl.subplot(2,3,2)
    pl.plot(f2,s2)
    pl.subplot(2,3,3)
    pl.plot(f3,s3)
    pl.subplot(2,3,4)
    pl.plot(f4,s4)
    pl.subplot(2,3,5)
    pl.plot(f5,s5)
    pl.subplot(2,3,6)
    pl.plot(f6,s6)
    
    f0,s0 = pdm(x,y)
    f1,s1 = pdm_py(x,y)
    pl.figure()
    pl.plot(f0,s0)
    pl.plot(f1,s1)
    
    
    
    pl.show()