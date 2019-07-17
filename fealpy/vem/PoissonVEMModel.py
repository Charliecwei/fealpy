import numpy as np
from scipy.sparse import coo_matrix, csc_matrix, csr_matrix, spdiags, eye

from ..functionspace.vem_space import VirtualElementSpace2d
from ..solver import solve
from ..boundarycondition import DirichletBC
from ..vem import doperator
from ..quadrature import PolygonMeshIntegralAlg
from ..quadrature import GaussLegendreQuadrature


class PoissonVEMModel():
    def __init__(self, pde, mesh, p=1, q=4):
        """
        Initialize a Poisson virtual element model.

        Parameters
        ----------
        self : PoissonVEMModel object
        pde :  PDE Model object
        mesh : PolygonMesh object
        p : int

        See Also
        --------

        Notes
        -----
        """
        self.space =VirtualElementSpace2d(mesh, p)
        self.mesh = self.space.mesh
        self.pde = pde
        self.uh = self.space.function()
        self.area = self.space.smspace.area
        self.integrator = mesh.integrator(q)

        self.integralalg = PolygonMeshIntegralAlg(
                self.integrator,
                self.mesh,
                area=self.area,
                barycenter=self.space.smspace.barycenter)

        self.uI = self.space.interpolation(pde.solution, self.integralalg.integral)

        self.mat = doperator.basic_matrix(self.space, self.area)

    def reinit(self, mesh, p):
        self.space =VirtualElementSpace2d(mesh, p)
        self.mesh = self.space.mesh
        self.uh = self.space.function()
        self.area = self.space.smspace.area

        self.integralalg = PolygonMeshIntegralAlg(
                self.integrator,
                self.mesh,
                area=self.area,
                barycenter=self.space.smspace.barycenter)

        self.uI = self.space.interpolation(
                self.pde.solution, self.integralalg.integral)

        self.mat = doperator.basic_matrix(self.space, self.area)


    def project_to_smspace(self, uh=None):
        p = self.space.p
        cell2dof = self.space.dof.cell2dof
        cell2dofLocation = self.space.dof.cell2dofLocation
        cd = np.hsplit(cell2dof, cell2dofLocation[1:-1])
        if uh is None:
            g = lambda x: x[0]@self.uh[x[1]]
        else:
            g = lambda x: x[0]@uh[x[1]]
        S = self.space.smspace.function()
        S[:] = np.concatenate(list(map(g, zip(self.mat.PI1, cd))))
        return S

    def recover_estimate(self, uh=None, rtype='simple', residual=True,
            returnsup=False):
        """
        estimate the recover-type error

        Parameters
        ----------
        self : PoissonVEMModel object
        rtype : str
            'simple':
            'area'
            'inv_area'

        See Also
        --------

        Notes
        -----

        """
        space = self.space
        mesh = space.mesh
        NC = mesh.number_of_cells()
        NV = mesh.number_of_vertices_of_cells()
        cell = mesh.entity('cell')
        barycenter = space.smspace.barycenter

        h = space.smspace.h
        area = space.smspace.area
        ldof = space.smspace.number_of_local_dofs()

        # project the vem solution into linear polynomial space
        idx = np.repeat(range(NC), NV)
        if uh is None:
            S = self.project_to_smspace(self.uh)
        else:
            S = self.project_to_smspace(uh)

        grad = S.grad_value(barycenter)
        S0 = space.smspace.function()
        S1 = space.smspace.function()
        n2c = mesh.ds.node_to_cell()
        try:
            isSubDomain = self.pde.subdomain(barycenter)
            for isFlag in isSubDomain:
                isSubIdx = np.repeat(isFlag, NV)
                M = n2c[:, isFlag]
                sa = area[isFlag]
                if rtype is 'simple':
                    d = n2c.sum(axis=1)
                    ruh = np.asarray((M@grad[isFlag])/d.reshape(-1, 1))
                elif rtype is 'area':
                    d = n2c@area
                    ruh = np.asarray((M@(grad[isFlag]*sa.reshape(-1, 1)))/d.reshape(-1, 1))
                elif rtype is 'inv_area':
                    d = n2c@(1/area)
                    ruh = np.asarray((M@(grad[isFlag]/sa.reshape(-1, 1)))/d.reshape(-1, 1))
                else:
                    raise ValueError("I have note code method: {}!".format(rtype))

                for i in range(3):
                    S0[i::ldof] += np.bincount(
                            idx[isSubIdx],
                            weights=self.mat.B[i, isSubIdx]*ruh[cell[isSubIdx], 0],
                            minlength=NC)
                    S1[i::ldof] += np.bincount(
                            idx[isSubIdx],
                            weights=self.mat.B[i, isSubIdx]*ruh[cell[isSubIdx], 1],
                            minlength=NC)

        except  AttributeError:
            if rtype is 'simple':
                d = n2c.sum(axis=1)
                ruh = np.asarray((n2c@grad)/d.reshape(-1, 1))
            elif rtype is 'area':
                d = n2c@area
                ruh = np.asarray((n2c@(grad*area.reshape(-1, 1)))/d.reshape(-1, 1))
            elif rtype is 'inv_area':
                d = n2c@(1/area)
                ruh = np.asarray((n2c@(grad/area.reshape(-1,1)))/d.reshape(-1, 1))
            else:
                raise ValueError("I have note code method: {}!".format(rtype))

            for i in range(ldof):
                S0[i::ldof] = np.bincount(
                        idx,
                        weights=self.mat.B[i, :]*ruh[cell, 0],
                        minlength=NC)
                S1[i::ldof] = np.bincount(
                        idx,
                        weights=self.mat.B[i, :]*ruh[cell, 1],
                        minlength=NC)

        try:
            k = self.pde.diffusion_coefficient(barycenter)
        except  AttributeError:
            k = np.ones(NC)

        node = mesh.node
        gx = S0.value(node[cell], idx) - np.repeat(grad[:, 0], NV)
        gy = S1.value(node[cell], idx) - np.repeat(grad[:, 1], NV)
        eta = k*np.bincount(idx, weights=gx**2+gy**2)/NV*area

        if residual is True:
            fh = self.integralalg.fun_integral(self.pde.source, True)/self.area
            g0 = S0.grad_value(barycenter)
            g1 = S1.grad_value(barycenter)
            eta += (fh + k*(g0[:, 0] + g1[:, 1]))**2*area**2

        if returnsup is True:
            def f(x, cellidx):
                pass

        return np.sqrt(eta)

    def get_left_matrix(self):
        space = self.space
        area = self.area
        try:
            a = self.pde.diffusion_coefficient
            return doperator.stiff_matrix(space, area, cfun=a, mat=self.mat)
        except AttributeError:
            return doperator.stiff_matrix(space, area, mat=self.mat)

    def get_right_vector(self):
        f = self.pde.source
        integral = self.integralalg.integral
        return doperator.source_vector(
                integral,
                f,
                self.space,
                self.mat.PI0)

    def solve(self):
        uh = self.uh
        bc = DirichletBC(self.space, self.pde.dirichlet)
        self.A, b = solve(self, uh, dirichlet=bc, solver='direct')

    def l2_error(self):
        e = self.uh - self.uI
        return np.sqrt(np.mean(e**2))

    def uIuh_error(self):
        e = self.uh - self.uI
        return np.sqrt(e@self.A@e)

    def L2_error(self):
        u = self.pde.solution
        S = self.project_to_smspace(self.uh)
        uh = S.value
        return self.integralalg.L2_error(u, uh)

    def H1_semi_error(self):
        gu = self.pde.gradient
        S = self.project_to_smspace(self.uh)
        guh = S.grad_value
        e = self.integralalg.L2_error(gu, guh)
        return e

    def L2_error_Kellogg(self):
        u = self.pde.solution
        S = self.project_to_smspace(self.uh)
        uh = S.value
        e = self.integralalg.L2_error(u, uh, celltype=True)

        NC = self.mesh.number_of_cells()
        NV = self.mesh.number_of_nodes_of_cells()

        node = self.mesh.entity('node')
        cell = self.mesh.entity('cell')
        isOrgin = (np.sum(node == 0.0, axis=-1) == 2)
        flag = np.zeros(NC, dtype=np.int)
        idx = np.repeat(range(NC), NV)
        np.add.at(flag, idx, isOrgin[cell])
        isBadCell = (flag > 0)
        e = np.sqrt(np.sum(e[~isBadCell]**2))
        return e

    def H1_semi_error_Kellogg(self):
        gu = self.pde.gradient
        S = self.project_to_smspace(self.uh)
        guh = S.grad_value
        e = self.integralalg.L2_error(gu, guh, celltype=True)

        NC = self.mesh.number_of_cells()
        NV = self.mesh.number_of_nodes_of_cells()

        node = self.mesh.entity('node')
        cell = self.mesh.entity('cell')
        isOrgin = (np.sum(node == 0.0, axis=-1) == 2)
        flag = np.zeros(NC, dtype=np.int)
        idx = np.repeat(range(NC), NV)
        np.add.at(flag, idx, isOrgin[cell])
        isBadCell = (flag > 0)
        e = np.sqrt(np.sum(e[~isBadCell]**2))
        return e

    def H1_semi_error_Kellogg_1(self):
        """

        """
        wh = self.space.function()
        isBdDof = self.space.boundary_dof()
        wh[isBdDof] = self.uh[isBdDof]

        uh = self.project_to_smspace(self.uh)
        guh = uh.grad_value
        wh = self.project_to_smspace(wh)
        gwh = wh.grad_value
        gu = self.pde.gradient

        def f(x, cellidx):
            val0 = gu(x) - guh(x, cellidx)
            val1 = gwh(x, cellidx)
            val = np.sum(val0*val1, axis=-1)
            return val

        e = self.integralalg.integral(f, celltype=True)

        barycenter = self.space.smspace.barycenter
        k = self.pde.diffusion_coefficient(barycenter)
        e *= k

        # 边界单元积分
        mesh = self.mesh
        isBdCell = mesh.ds.boundary_cell_flag()
        e = np.sum(e[isBdCell])

        # 边界边上的积分
        node = mesh.entity('node')
        edge = mesh.entity('edge')
        isBdEdge = mesh.ds.boundary_edge_flag()
        n = mesh.edge_normal(index=isBdEdge)

        qf = GaussLegendreQuadrature(8)
        bcs, ws = qf.quadpts, qf.weights
        edge2cell = mesh.ds.edge_to_cell()
        cidx = edge2cell[isBdEdge, 0]
        k = k[cidx]
        pts = np.einsum('ij, kjm->ikm', bcs, node[edge[isBdEdge]])
        uval = self.pde.solution(pts)
        guval = np.einsum('ikm, km->ik', self.pde.gradient(pts), n)
        uhval = np.einsum('ij, kj->ik', bcs, self.uh[edge[isBdEdge]])

        e1 = np.einsum('i, ik, k->k', ws, (uval - uhval)*guval, k)
        e = e1.sum() - e

        return np.sqrt(e)
