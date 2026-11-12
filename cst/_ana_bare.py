import numpy as np
c=299792458.0; Z0=376.730313668; er=2.65; h=1.5e-3
def ana(f):
    k0=2*np.pi*f*1e9/c; beta=k0*np.sqrt(er); zd=Z0/np.sqrt(er)
    zin=1j*zd*np.tan(beta*h)
    return (zin-Z0)/(zin+Z0)
cst={9.0:-15.9016,9.5:-26.9706,10.0:-38.0713,10.5:-49.2051,11.0:-60.3752}
print(" f     ana_ph    cst_ph   cst-ana   implied_d(mm)  prop(7.49mm)")
for f,ph in cst.items():
    a=np.degrees(np.angle(ana(f)))
    d=(ph-a+180)%360-180
    k0=2*np.pi*f*1e9/c
    dimp=-np.radians(d)/(2*k0)*1e3
    prop=-np.degrees(2*k0*7.49e-3)
    prop=(prop+180)%360-180
    print("%4.1f  %8.3f  %8.3f  %8.3f   %8.3f      %8.3f"%(f,a,ph,d,dimp,prop))
