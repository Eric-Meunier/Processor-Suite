# import numpy as np
# import matplotlib.pyplot as plt
# from magpylib.source.magnet import Box,Cylinder
# from magpylib import Collection, displaySystem
#
# # create magnets
# s1 = Box(mag=(0,0,600), dim=(3,3,3), pos=(-4,0,3))
# s2 = Cylinder(mag=(0,0,500), dim=(3,5))
#
# # create collection
# c = Collection(s1,s2)
#
# # manipulate magnets individually
# s1.rotate(45,(0,1,0), anchor=(0,0,0))
# s2.move((5,0,-4))
#
# # manipulate collection
# c.move((-2,0,0))
#
# # calculate B-field on a grid
# xs = np.linspace(-10,10,33)
# zs = np.linspace(-10,10,44)
# POS = np.array([(x,0,z) for z in zs for x in xs])
# Bs = c.getB(POS).reshape(44,33,3)     #<--VECTORIZED
#
# # create figure
# fig = plt.figure(figsize=(9,5))
# ax1 = fig.add_subplot(121, projection='3d')  # 3D-axis
# ax2 = fig.add_subplot(122)                   # 2D-axis
#
# # display system geometry on ax1
# displaySystem(c, subplotAx=ax1, suppress=True)
#
# # display field in xz-plane using matplotlib
# X,Z = np.meshgrid(xs,zs)
# U,V = Bs[:,:,0], Bs[:,:,2]
# ax2.streamplot(X, Z, U, V, color=np.log(U**2+V**2))
#
# plt.show()

import numpy as np
import matplotlib.pyplot as plt
from src.mag_field import wire
from src.mag_field import biotsavart


# simple solenoid
# approximated analytical solution: B = mu0 * I * n / l = 4*pi*1e-7[T*m/A] * 100[A] * 10 / 0.5[m] = 2.5mT


# w = wire.Wire(path=wire.Wire.SolenoidPath(pitch=0.05, turns=10), discretization_length=0.01, current=100).Rotate(axis=(1, 0, 0), deg=90) #.Translate((0.1, 0.1, 0)).
path = np.array([[0,0,0],[0,1,0], [1,1,0], [1,0,0]])
w = wire.Wire(path=path) #.Translate((0.1, 0.1, 0)).
sol = biotsavart.BiotSavart(wire=w)

resolution = 0.04
volume_corner1 = (-.2, -.8, -.2)
volume_corner2 = (.2+1e-10, .3, .2)

# matplotlib plot 2D
# create list of xy coordinates
grid = np.mgrid[volume_corner1[0]:volume_corner2[0]:resolution, volume_corner1[1]:volume_corner2[1]:resolution]

# create list of grid points
points = np.vstack(map(np.ravel, grid)).T
points = np.hstack([points, np.zeros([len(points),1])])

# calculate B field at given points
B = sol.CalculateB(points=points)


Babs = np.linalg.norm(B, axis=1)

# remove big values close to the wire
cutoff = 0.005

B[Babs > cutoff] = [np.nan,np.nan,np.nan]
#Babs[Babs > cutoff] = np.nan

for ba in B:
    print(ba)

#2d quiver
# get 2D values from one plane with Z = 0

fig = plt.figure()
ax = fig.gca()
ax.plot(path[:,0], path[:,1])
ax.quiver(points[:, 0], points[:, 1], B[:, 0], B[:, 1], scale=.15)
X = np.unique(points[:, 0])
Y = np.unique(points[:, 1])
cs = ax.contour(X, Y, Babs.reshape([len(X), len(Y)]).T, 10)
# ax.clabel(cs)
plt.xlabel('x')
plt.ylabel('y')
plt.axis('equal')
plt.show()


# # matplotlib plot 3D
#
# grid = np.mgrid[volume_corner1[0]:volume_corner2[0]:resolution*2, volume_corner1[1]:volume_corner2[1]:resolution*2, volume_corner1[2]:volume_corner2[2]:resolution*2]
#
# # create list of grid points
# points = np.vstack(map(np.ravel, grid)).T
#
# # calculate B field at given points
# B = sol.CalculateB(points=points)
#
# Babs = np.linalg.norm(B, axis=1)
#
# fig = plt.figure()
# # 3d quiver
# ax = fig.gca(projection='3d')
# sol.mpl3d_PlotWires(ax)
# ax.quiver(points[:, 0], points[:, 1], points[:, 2], B[:, 0], B[:, 1], B[:, 2], length=0.04)
# plt.show()