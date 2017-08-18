import requests
import pandas
from StringIO import StringIO
import astropy.units as u
import astropy.constants as const
import EXOSIMS.PlanetPhysicalModel.Forecaster
from sqlalchemy import create_engine
import getpass,keyring
import numpy as np


#grab the data
query = """https://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/nph-nstedAPI?table=exoplanets&select=*&format=csv"""
r = requests.get(query)
data = pandas.read_csv(StringIO(r.content))

# we need:
# distance AND
# (sma OR (period AND stellar mass)) AND
# (radius OR mass (either true or m\sin(i)))
keep = ~np.isnan(data['st_dist']) & (~np.isnan(data['pl_orbsmax'].values) | \
        (~np.isnan(data['pl_orbper'].values) & ~np.isnan(data['st_mass'].values))) & \
       (~np.isnan(data['pl_bmassj'].values) | ~np.isnan(data['pl_radj'].values))
data = data[keep]

#fill in missing smas from period & star mass
nosma = np.isnan(data['pl_orbsmax'].values)
p2sma = lambda mu,T: ((mu*T**2/(4*np.pi**2))**(1/3.)).to('AU')
GMs = const.G*(data['st_mass'][nosma].values*u.solMass) # units of solar mass
T = data['pl_orbper'][nosma].values*u.day
tmpsma = p2sma(GMs,T)
data['pl_orbsmax'][nosma] = tmpsma
data = data.assign(smax_from_orbper=nosma)

#update all WAs based on sma
WA = np.arctan((data['pl_orbsmax'].values*u.AU)/(data['st_dist'].values*u.pc)).to('mas')
data['pl_angsep'] = WA.value

#populate max WA based on available eccentricity data (otherwise maxWA = WA)
hase = ~np.isnan(data['pl_orbeccen'].values)
maxWA = WA[:]
maxWA[hase] = np.arctan((data['pl_orbsmax'][hase].values*(1 + data['pl_orbeccen'][hase].values)*u.AU)/(data['st_dist'][hase].values*u.pc)).to('mas')
data = data.assign(pl_maxangsep=maxWA.value)

#populate min WA based on eccentricity & inclination data (otherwise minWA = WA)
hasI =  ~np.isnan(data['pl_orbincl'].values)
s = data['pl_orbsmax'].values*u.AU
s[hase] *= (1 - data['pl_orbeccen'][hase].values)
s[hasI] *= np.cos(data['pl_orbincl'][hasI].values*u.deg)
minWA = np.arctan(s/(data['st_dist'].values*u.pc)).to('mas')
data = data.assign(pl_minangsep=minWA.value)

#fill in radius based on median values generated by forecaster from best mass 
#noR = np.isnan(data['pl_radj'].values)
#fcstr = EXOSIMS.PlanetPhysicalModel.Forecaster.Forecaster()
#ms = data['pl_bmassj'][noR].values
#planradii = [np.median(fcstr.calc_radius_from_mass(np.array([v]*1000)*u.M_jupiter).to(u.R_jupiter).value) for v in ms]
#data['pl_radj'][noR] = planradii
#data = data.assign(rad_from_mass=noR)

#fill in radius based on forcaster best fit
noR = np.isnan(data['pl_radj'].values)

S = np.array([0.2790,0.589,-0.044,0.881])
C0 = np.log10(1.008)
T = np.array([2.04,((0.414*u.M_jupiter).to(u.M_earth)).value,((0.0800*u.M_sun).to(u.M_earth)).value])
C = np.hstack((C0, C0 + np.cumsum(-np.diff(S)*np.log10(T))))

m1 = np.array([1e-3,T[0]])
r1 = 10.**(C[0] + np.log10(m1)*S[0])

m2 = T[0:2]
r2 = 10.**(C[1] + np.log10(m2)*S[1])

m3 = T[1:3]
r3 = 10.**(C[2] + np.log10(m3)*S[2])

m = ((data['pl_bmassj'][noR].values*u.M_jupiter).to(u.M_earth)).value
def RfromM(m):
    m = np.array(m,ndmin=1)
    r = np.zeros(m.shape)
    inds = np.digitize(m,np.hstack((0,T,np.inf)))
    for j in range(1,inds.max()+1):
        r[inds == j] = 10.**(C[j-1] + np.log10(m[inds == j])*S[j-1])

    return r

r = RfromM(m)
data['pl_radj'][noR] = ((r*u.R_Earth).to(u.R_jupiter)).value
data = data.assign(rad_from_mass=noR)

#fill in effective temperatures
noteff = np.isnan(data['st_teff'].values)
bmv = data['st_bmvj'][noteff].values
nobv = np.isnan(bmv)

#Teff = 4600.0*u.K * (1.0/(0.92*self.BV[sInds] + 1.7) + 1.0/(0.92*self.BV[sInds] + 0.62))
#θeff = 0.5379 + 0.3981(V − I)+4.432e-2(V − I)**2 − 2.693e-2(V − I)**3


#orbit info
from EXOSIMS.util.eccanom import eccanom
from EXOSIMS.util.deltaMag import deltaMag
import EXOSIMS.Prototypes.PlanetPhysicalModel
PPMod = EXOSIMS.Prototypes.PlanetPhysicalModel.PlanetPhysicalModel()
M = np.linspace(0,2*np.pi,100)
plannames = data['pl_hostname'].values+' '+data['pl_letter'].values

orbdata = None
#row = data.iloc[71] 
for j in range(len(plannames)):
    print(plannames[j])
    row = data.iloc[j] 

    a = row['pl_orbsmax']
    e = row['pl_orbeccen'] 
    if np.isnan(e): e = 0.0
    I = row['pl_orbincl']*np.pi/180.0
    if np.isnan(I): I = np.pi/2.0
    w = row['pl_orblper']*np.pi/180.0
    if np.isnan(w): w = 0.0
    E = eccanom(M, e)                      
    Rp = row['pl_radj']
    dist = row['st_dist']

    a1 = np.cos(w) 
    a2 = np.cos(I)*np.sin(w)
    a3 = np.sin(I)*np.sin(w)
    A = a*np.vstack((a1, a2, a3))

    b1 = -np.sqrt(1 - e**2)*np.sin(w)
    b2 = np.sqrt(1 - e**2)*np.cos(I)*np.cos(w)
    b3 = np.sqrt(1 - e**2)*np.sin(I)*np.cos(w)
    B = a*np.vstack((b1, b2, b3))
    r1 = np.cos(E) - e
    r2 = np.sin(E)

    r = (A*r1 + B*r2).T
    d = np.linalg.norm(r, axis=1)
    s = np.linalg.norm(r[:,0:2], axis=1)
    phi = PPMod.calc_Phi(np.arccos(r[:,2]/d)*u.rad) 
    dMag = deltaMag(0.5, Rp*u.R_jupiter, d*u.AU, phi) 
    WA = np.arctan((s*u.AU)/(dist*u.pc)).to('mas').value


    out = pandas.DataFrame({'Name': [plannames[j]]*len(M),
                            'M': M,
                            'r': d,
                            's': s,
                            'phi': phi,
                            'dMag': dMag,
                            'WA': WA})
    if orbdata is None:
        orbdata = out.copy()
    else:
        orbdata = orbdata.append(out)



#------write to db------------

#testdb
engine = create_engine('mysql+pymysql://ds264@127.0.0.1/dsavrans_plandb',echo=False)
data.to_sql('KnownPlanets',engine,chunksize=100)

orbdata.to_sql('PlanetOrbits',engine,chunksize=100,if_exists='replace')



username = 'dsavrans_admin'
passwd = keyring.get_password('plandb_sql_login', username)
if passwd is None:
    passwd = getpass.getpass("Password for mysql user %s:\n"%username)
    keyring.set_password('plandb_sql_login', username, passwd)


#proddb
engine = create_engine('mysql+pymysql://'+username+':'+passwd+'@sioslab.com/dsavrans_plandb',echo=False)
data.to_sql('KnownPlanets',engine,chunksize=100)
orbdata.to_sql('PlanetOrbits',engine,chunksize=100,if_exists='replace')



#todo: fill in inclinations
