import numpy as np

from ..mesh import TriangleMesh, QuadrangleMesh
from ..mesh.tree_data_structure import Quadtree

class ObstacleData1:
    def __init__(self):
        pass

    def init_mesh(self, n=4, meshtype='quadtree'):
        point = np.array([
            (0, 0),
            (1, 0),
            (1, 1),
            (0, 1)], dtype=np.float)
        if meshtype is 'quadtree':
            cell = np.array([(0, 1, 2, 3)], dtype=np.int)
            mesh = Quadtree(point, cell)
            mesh.uniform_refine(n)
            return mesh
        elif meshtype is 'quad':
            cell = np.array([(0, 1, 2, 3)], dtype=np.int)
            mesh = QuadrangleMesh(point, cell)
            mesh.uniform_refine(n)
            return mesh
        elif meshtype is 'tri':
            cell = np.array([(1, 2, 0), (3, 0, 2)], dtype=np.int)
            mesh = TriangleMesh(point, cell)
            mesh.uniform_refine(n)
            return mesh
        else:
            raise ValueError("".format)

    def source(self, p):
        """The right hand side
        """
        val = -8*np.ones(p.shape[0:-1])
        return val

    def obstacle(self, p):
        """The obstacle function
        """
        val = -0.3*np.ones(p.shape[0:-1])
        return val 

    def dirichlet(self, p):
        return np.zeros(p.shape[0:-1]) 


class ObstacleData2:
    def __init__(self):
        self.r0 = 0.6979651482

    def init_mesh(self, n=4, meshtype='quadtree'):
        point = np.array([
            (-2, -2),
            ( 2, -2),
            ( 2,  2),
            (-2,  2)], dtype=np.float)
        if meshtype is 'quadtree':
            cell = np.array([(0, 1, 2, 3)], dtype=np.int)
            mesh = Quadtree(point, cell)
            mesh.uniform_refine(n)
            return mesh
        elif meshtype is 'quad':
            cell = np.array([(0, 1, 2, 3)], dtype=np.int)
            mesh = QuadrangleMesh(point, cell)
            mesh.uniform_refine(n)
            return mesh
        elif meshtype is 'tri':
            cell = np.array([(1, 2, 0), (3, 0, 2)], dtype=np.int)
            mesh = TriangleMesh(point, cell)
            mesh.uniform_refine(n)
            return mesh
        else:
            raise ValueError("".format)

    def solution(self, p):
        x = p[..., 0]
        y = p[..., 1]
        r0 = self.r0
        r = np.sqrt((x*x+y*y))
        val = np.zeros(p.shape[0:-1], dtype=np.float)
        flag = (r <= r0)
        val[flag] = np.sqrt(1 - r[flag]**2)
        val[~flag] = -r0**2*np.log(r[~flag]/2)/np.sqrt(1-r0**2)
        return val
 
    def gradient(self, p):
        x = p[..., 0]
        y = p[..., 1]
        r0 = self.r0
        r = np.sqrt((x*x+y*y))
        val = np.zeros(p.shape, dtype=np.float)
        flag = (r <= self.r0)
        val[flag,  0] = -x[flag]/np.sqrt(-r[flag]**2 + 1)
        val[flag,  1] = -y[flag]/np.sqrt(-r[flag]**2 + 1)
        val[~flag, 0] = -r0**2*x[~flag]/np.sqrt(-r0**2 + 1)/r[~flag]
        val[~flag, 1] = -r0**2*y[~flag]/np.sqrt(-r0**2 + 1)/r[~flag]

        return val

    def source(self, p):
        val = np.zeros(p.shape[0:-1])
        return val

    def obstacle(self, p):

        x = p[..., 0]
        y = p[..., 1]
        r = np.sqrt((x*x+y*y))
        val = np.zeros(p.shape[0:-1], dtype=np.float)
        flag = (r <= 1)
        val[flag] = r[flag]
        val[~flag] = -1
        return val

    def dirichlet(self, p):
        return self.solution(p)
