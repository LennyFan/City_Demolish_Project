################################################################################
#
# Module: CTILP_Optimization.py
# Description: OSMnx, Gurobi, LP, ILP
#              OSMNX from https://github.com/gboeing/osmnx Author: gboeing
# Auther: Lenny Fan (Chi-Wen Fan)
################################################################################

import osmnx as ox  
import pandas as pd  
import numpy as np
from gurobipy import *
from shapely import geometry  # geometry.Polygon
import csv
from ast import literal_eval as make_tuple
import networkx as nx
import math

# Building footprint (plus street network) figure-ground diagrams
#import matplotlib.pyplot as plt
from IPython.display import Image

# configure the inline image display
ox.config(log_console=True, use_cache=True)
img_folder = 'images'
extension = 'png'
image_size = 1000


################################################################################
#
# Inport data: vacantosmnx - vacant houses ID in the area 
#       ox.buildings_from_address('1516 Kenhill Ave, Baltimore, MD', distance=550)
#
################################################################################

with open('vacantosmnx', 'rb') as f:
    reader = csv.reader(f)
    # vacantosmnx : list[int] - list of all vacant houses id
    vacantosmnx = map(int,list(reader)[0])



################################################################################
#
# Class OSMNX_Map 
#      Parameters - address(Sring): default is '1516 Kenhill Ave, Baltimore, MD'
#                   radius(int): the radius from the address, default is 80
#                   same(bool): if True randomly generating the house height, 
#                               defaul is Fasle setting house to be two story                             
#      
################################################################################

class OSMNX_Map(object):
    def __init__(self, address='1516 Kenhill Ave, Baltimore, MD', radius=80, same = False):
        
        self.address = address
        self.radius = radius
        
        # GEOdataFrame
        #    addr:city
        #    addr:country
        #    addr:housenumber
        #    addr:postcode
        #    addr:state
        #    addr:street
        #    building("yes","no")
        #    amenity, name, religion, denomination
        #    geometry 
        #    nodes
        # < check week6_xx.ipython to get more detail >
        self.gdf = ox.buildings_from_address(address, distance=radius)
        #
        # add new column centroid - the centrel point of house
        self.gdf = self.gdf.assign(centroid = self.gdf['geometry'].centroid)
        
        # initialize the model
        self.initial_housetype()
        self.initial_storytype(same = same)
        
        # 
        self.Edge = self.GetEdgeSet_OSMNX()
        self.Houses = self.GetHouseSet_OSMNX()
        self.Owners = self.GetOwnerSet_OSMNX()
        self.Renters = self.GetRenterSet_OSMNX()
        self.Vacants = self.GetVacantSet_OSMNX()
        
        #self.initial_price()
        #self.CompareHouses = GetCompareHousesSet_OSMNX()

        
    def initial_housetype(self):
        """
        update gdf by adding column 'housetype' take integer value
            -1 : nonstructure
            0  : rentor
            1  : owner
            2  : vacant
            3  : not target ( if no address for the building or the area of buildig > 398 )
            50 : curch
            100: police
        """
        # add new column 'housetype'
        sLength = len(self.gdf[self.gdf.columns[0]])
        self.gdf = self.gdf.assign(
            housetype=pd.Series(np.zeros(len(self.gdf[self.gdf.columns[0]]),dtype = int)).values) 
        
        # set vacant house
        for i in vacantosmnx:
            if i in self.gdf.index:
                self.gdf.loc[i,'housetype'] = 2     
        self.gdf_proj = ox.project_gdf(self.gdf)
        
        
        # set other types of building
        for i in self.gdf.index:
            # if it's not building
            # note that no wall for this
            if self.gdf['building'][i] != 'yes':
                self.gdf.loc[i,'housetype'] = -1
            # if it's amenity = police
            elif {'amenity'}.issubset(self.gdf.columns) and self.gdf['amenity'][i] == 'police':
                self.gdf.loc[i,'housetype'] = 100
            # if it's amenity = place_of_worship
            elif {'amenity'}.issubset(self.gdf.columns) and self.gdf['amenity'][i] == 'place_of_worship':
                self.gdf.loc[i,'housetype'] = 50
            # if no address for the building or the area of buildig > 398
            # option: area > 125 or area < 37
            elif pd.isnull(self.gdf['addr:street'][i]) or self.gdf_proj.area[i] > 398 : 
                self.gdf.loc[i,'housetype'] = 3
                
        # update gdf_proj
        # 10.20.2017 [ to be updated ] not sure if it's neccessary to have this
        self.gdf_proj = ox.project_gdf(self.gdf)

        
    def initial_storytype(self, same = False):
        """
        update gdf by adding column 'housetype' take integer value
        
        if same is True, then only take integer value 2 in the column
        else randomly assign 2 or 3 into the column
        """
        sLength = len(self.gdf[self.gdf.columns[0]])
        if not same:        
            self.gdf = self.gdf.assign(storytype= np.random.randint(2,4,size = sLength))
        else:
            self.gdf = self.gdf.assign(storytype= np.random.randint(2,3,size = sLength))
            
        
    def GetEdgeSet_OSMNX(self):
        """
        Inport data: Edge550 - adjacent houses set in 
                ox.buildings_from_address('1516 Kenhill Ave, Baltimore, MD', distance=550)
                
        get edge set
        """
        
        # get tuple set
        # it take a while to get edge set
        # I will recommend the usre to get edges separatly and save into a txt or csv file
        # < check week6_xx.ipython to get more detail >
        if self.radius == 550:
            
            with open('Edge550', 'rb') as f:
                reader = csv.reader(f)
                E = list(reader)[0]
                
            for i in xrange(len(E)):
                E[i] = make_tuple(E[i])
 
        else:
        
            E = []
            print np.unique(self.gdf['housetype'])
            
            # very important step
            # if there is no structure
            # there is no need to consider the wall, which means there is no edge conntected to 
            # x_i if the i-th row item is nonstructure
            gdf = self.gdf[self.gdf['housetype'] != -1]
            
            for i in xrange(len(gdf.index)):
                for j in xrange(i+1,len(gdf.index)):
                    
                    for node in gdf['nodes'][gdf.index[i]]:
                        if node in gdf['nodes'][gdf.index[j]]:
                            E.append((gdf.index[i],gdf.index[j]))
                            break
        return E
    
    
    def GetHouseSet_OSMNX(self):
        """        
        get House set - list of house id if housetype != -1
        """
        H = self.gdf[self.gdf['housetype'] != -1].index.tolist()
        return H

    
    def GetRenterSet_OSMNX(self):
        """        
        get renter houses set - list of house id if housetype == 0
        """
        R = []
        for i in self.gdf.index:
            if self.gdf['housetype'][i] == 0:
                R.append(i)
        return R
    
    
    def GetOwnerSet_OSMNX(self):
        """        
        get owner houses set - list of house id if housetype == 1
        """
        O = []
        for i in self.gdf.index:
            if self.gdf['housetype'][i] == 1:
                O.append(i)
        return O
    
    
    def GetVacantSet_OSMNX(self):
        """        
        get vacant houses set - list of house id if housetype == 2
        """
        V = []
        for i in self.gdf.index:
            if self.gdf['housetype'][i] == 2:
                V.append(i)
        return V
    
    def GetCompareHousesSet_OSMNX(self):
        """        
        get compare houses set - (O+R)*V
        """
        C = []
        for owner in self.Owners:
            for vacant in self.Vacants:
                C.append((owner,vacant))
        for renter in self.Renters:
            for vacant in self.Vacants:
                C.append((renter,vacant))
        return C
    
    def plot(self, x = None, size = 9, name = 'temp_image', network_type='walk', dpi=90, 
             default_width=5, street_widths=None):
        """        
        plot the map
        Parameters - x(model.x): default None, variables x after optimization
                     size(int) : default 9
                     name(string) : default 'temp_image', the saved image name
                     network_type(string) : default walk
                     dpi(int) : default 90
                     default_width(int) : default 5
                     street_widths(int) : default None
        """
        # default color set - before optimization
        ec = []
        for i in self.gdf.index:
            # white color for vacant houses
            if self.gdf['housetype'][i] == 2:
                ec.append('w')
            # yellow color for police station
            elif self.gdf['amenity'][i] == 'police':
                ec.append('yellow')
            # light green for curch
            elif self.gdf['amenity'][i] == 'place_of_worship':
                ec.append('#d7ff6e')
            # red color for non structure 
            elif self.gdf['building'][i] != 'yes': 
                ec.append('r')
            # #ff6060 for area > 398
            elif (pd.isnull(self.gdf['addr:street'][i]) 
                  and self.gdf_proj.area[i] > 398)or self.gdf_proj.area[i] > 398 : 
                ec.append('#ff6060')
            # #8e8e8e for no address
            elif pd.isnull(self.gdf['addr:street'][i])  : 
                ec.append('#8e8e8e')
            # #ffcf77 for renter houses
            elif self.gdf['housetype'][i] == 0:
                ec.append('#ffcf77')   
            # #ffcf77 for owner houses
            elif self.gdf['housetype'][i] == 1:
                ec.append('orange')
            # blue coloe fo o.w., which means the model is not correct
            else:
                ec.append('blue') 
                
        # plot the original map before optimization
        if x == None:
            #ox.plot_buildings(self.gdf, figsize = (size,size) ,color = ec, bgcolor = "aliceblue")
            
            # get gdf_proj
            gdf_proj = ox.project_gdf(self.gdf)
            # initial figure ground
            fig, ax = ox.plot_figure_ground(address=self.address, dist=self.radius, 
                                            network_type=network_type, default_width=default_width,
                                            bgcolor='#333333',edge_color = 'w',
                                            street_widths=street_widths, save=False, show=False, close=True, 
                                            fig_length = size)
            # plot the building
            fig, ax = ox.plot_buildings(gdf_proj, fig=fig, ax=ax, color=ec, set_bounds=True,
                                        save=True, show=False, close=True, filename=name, 
                                        dpi=dpi)
            # save image
            Image('{}/{}.{}'.format(img_folder, name, extension),height = image_size,width= image_size)
            
            return fig,ax 
        
        # after optimization
        else:
            
            # update color set
            # if x == 1 or very close to 1 (tolerance)
            ec_after = ['mediumseagreen' if x[self.Houses[i]].X == 1.0 or abs(x[self.Houses[i]].X - 1.0) < 0.000001 
                        else ec[i] for i in xrange(len(self.Houses))]
            
            # get gdf_proj
            gdf_proj = ox.project_gdf(self.gdf)
            # initial figure ground
            fig, ax = ox.plot_figure_ground(address=self.address, dist=self.radius, 
                                            network_type=network_type, default_width=default_width,
                                            bgcolor='#333333',edge_color = 'w',
                                            street_widths=street_widths, save=False, show=False, close=True, 
                                            fig_length = size)
            # plot the building
            fig, ax = ox.plot_buildings(gdf_proj, fig=fig, ax=ax, color=ec_after, set_bounds=True,
                                        save=True, show=False, close=True, filename=name, 
                                        dpi=dpi)
            # save image
            Image('{}/{}.{}'.format(img_folder, name, extension),height = image_size,width= image_size)
            
            return fig,ax 
            
            
            
################################################################################
#
# Class ILP_sol 
#      Parameters - Houses(list(string)) : the index of houses set 
#                   Edge(list(tuple))     
#                   gdf(GEOdataFrame)
#      
################################################################################
            
class ILP_sol(object):
    def __init__(self, Houses, Edge, gdf = False):
        """        
        Houses( list(id) ): Houses set
        Edge( list((id_1,id_2)) ) : All pairs of adjacent houses
        gdf( GEOdataframe ) : Default is False, if using other types of data, then you should update the code
                              from line 365 to line 366.
        """
        
        self.Houses = Houses
        self.Edge = Edge        
        self.gdf = gdf
        
        # initial iterator
        self.iter = 0
        # initial status
        self.status = []
        
        # if the input data type is not GEOdataframe
        if gdf is False:
            print "to be updated"
            
        else:
            # initial price
            self.initial_price()
            # initial gurobi model
            self.model = Model()
            
            # initial variables
            self.x = self.model.addVars(Houses,vtype = GRB.BINARY,name = "x")
            self.z = self.model.addVars(Edge,vtype = GRB.BINARY,name = "z")
            self.y = self.model.addVars(Edge,vtype = GRB.BINARY,name = "y")
            
            # if the building type >= 3, add constraint to set them all to be zero
            notakedown = self.model.addConstrs((self.x[i] == 0 
                              for i in self.gdf[self.gdf['housetype'] >= 3].index
                             ),name = "notakedown")
            # model update
            self.model.update()
            
        
        
    def initial_price(self,Budget = 185000,demolish_2_story = 13000,demolish_3_story = 22000,r_relocate = 85000,
                      o_relocate = 170000,wall_2_story = 14000,wall_3_story =25000,cost_reduction = 0):
        """        
        Budget : 
        demolish_2_story :
        demolish_3_story :
        r_relocate :
        o_relocate :
        wall_2_story :
        wall_3_story :
        cost_reduction :
        """
        self.Budget = Budget
        self.demolish_2_story = demolish_2_story
        self.demolish_3_story = demolish_3_story
        self.r_relocate = r_relocate
        self.o_relocate = o_relocate
        self.wall_2_story = wall_2_story
        self.wall_3_story =wall_3_story
        self.cost_reduction = cost_reduction
        
        # set the budget
        self.set_budget()
        
    def set_budget(self):
        """        
        add budget list
        """
        # if data type is geodataframe
        if self.gdf is not False :
            
            gdf = self.gdf
            
            # cost for demolishing house i for i in houses set
            self.Cost = [( self.demolish_2_story if gdf['storytype'][i] == 2 else 0 ) +
                         ( self.demolish_3_story if gdf['storytype'][i] == 3 else 0 ) +
                         ( self.r_relocate       if gdf['housetype'][i] == 0 else 0 ) +
                         ( self.o_relocate       if gdf['housetype'][i] == 1 else 0 ) 
                           for i in self.Houses]
            
            # cost for wall
            self.Wallij = [( self.wall_2_story/2 if gdf['storytype'][item[0]] == 2 else 0 ) +
                           ( self.wall_2_story/2 if gdf['storytype'][item[1]] == 2 else 0 ) +
                           ( self.wall_3_story/2 if gdf['storytype'][item[0]] == 3 else 0 ) + 
                           ( self.wall_3_story/2 if gdf['storytype'][item[1]] == 3 else 0 )
                             for item in self.Edge]
            
            self.Walli = [( self.wall_2_story if gdf['storytype'][self.Edge[i][0]] == 2 else 0 ) +
                          ( self.wall_3_story if gdf['storytype'][self.Edge[i][0]] == 3 else 0 ) - 
                            self.Wallij[i]
                            for i in xrange(len(self.Edge))]

            self.Wallj = [( self.wall_2_story if gdf['storytype'][self.Edge[i][1]] == 2 else 0 ) +
                          ( self.wall_3_story if gdf['storytype'][self.Edge[i][1]] == 3 else 0 ) - 
                            self.Wallij[i]
                            for i in xrange(len(self.Edge))]
            
            # benefit
            self.Benefit = [ self.cost_reduction for i in xrange(len(self.Edge))]
    
    
    def update_model_OSMNX(self,d ,h,
                           CompareHouses = False, Max = False, d_e = 30, power = 1, 
                           delta_method = True, model = 2):
        """        
        update momdel
        [ can be simplified ] 
        d( func() ) : distance function - distance_OSMNX 
        h( func() ) : weight function - affect_OSMNX 
        CompareHouses( list((id_1,id_2)) ) : the list of all pairs of occupied houses id and vacant houses id
                                             you can create your own list
        Max( bool ) : Default False. [ to be updated ]
        d_e( int ) : the effective distance. Default is 30 meters.
        power( int ) : the power of weight function ( 1/2^power ). Default is 1.
                       if power is 0. The weight function will be an indicator function
        delta_method( bool ) : If true use delta_method( O(n^2) space, no tolerance ). Default is True
        model( int ) : Can be either 1,2 or 3. [ to be filled ]. Default is 2
        """
        
        Houses = self.Houses
        Edge = self.Edge
        Cost = self.Cost
        Wallij = self.Wallij
        Walli = self.Walli
        Wallj = self.Wallj
        Benefit = self.Benefit
        
        
        # budget constraint
        Budget_Constraint = self.model.addConstr((quicksum(Cost[i]*self.x[Houses[i]] for i in xrange(len(Houses))) +
                             quicksum(Wallij[i]*self.z[Edge[i]] for i in xrange(len(Edge))) -
                             quicksum(Benefit[i]*self.y[Edge[i]] for i in xrange(len(Edge))) -
                             quicksum(Walli[i]*self.x[Edge[i][0]] for i in xrange(len(Edge))) -
                             quicksum(Wallj[i]*self.x[Edge[i][1]] for i in xrange(len(Edge))) 
                             <= 
                             self.Budget -
                             quicksum(Walli) - quicksum(Wallj)
                            )
                             , name = "Budget_Constraint")
        
        # set the boundary for zij
        # zij == 1 iff xi + xj = 1
        XOR1 = self.model.addConstrs((self.x[Edge[i][0]] - self.x[Edge[i][1]] - self.z[Edge[i]] <= 0 
                              for i in xrange(len(Edge))
                             ),name = "XOR1")
        XOR2 = self.model.addConstrs((self.x[Edge[i][1]] - self.x[Edge[i][0]] - self.z[Edge[i]] <= 0 
                              for i in xrange(len(Edge))
                             ),name = "XOR2")
        XOR3 = self.model.addConstrs((self.x[Edge[i][1]] + self.x[Edge[i][0]] + self.z[Edge[i]] <= 2 
                              for i in xrange(len(Edge))
                             ),name = "XOR3")
        XOR4 = self.model.addConstrs((-self.x[Edge[i][1]] - self.x[Edge[i][0]] + self.z[Edge[i]] <= 0 
                              for i in xrange(len(Edge))
                             ),name = "XOR4")

        # set the boundary for yij
        # yij == 1 iff xi*xj = 1
        CD1 = self.model.addConstrs((self.x[Edge[i][1]] + self.x[Edge[i][0]] - self.y[Edge[i]] <= 1 
                              for i in xrange(len(Edge))
                             ),name = "CD1")

        CD2 = self.model.addConstrs((-self.x[Edge[i][1]]  + self.y[Edge[i]] <= 0 
                              for i in xrange(len(Edge))
                             ),name = "CD2")

        CD3 = self.model.addConstrs((-self.x[Edge[i][0]]  + self.y[Edge[i]] <= 0 
                              for i in xrange(len(Edge))
                             ),name = "CD3")
        
        
        
        # to get the unique occupied houses set
        #                    vacant  houses set
        # [ can be improved ] 
        occupied = [item[0] for item in CompareHouses]
        occupied = np.unique(occupied)
        vacant = [item[1] for item in CompareHouses]
        vacant = np.unique(vacant)
        
        
        # there are three model
        # 1 : original delta method
        # 2 : 
        if delta_method:
            
            
            # create new variable 
            # delta_ij = (1-x_i)*(1-x_j) for all i in Occupied set and all j in vacant set
            # Worst Case: O(n^2) space 
            if model == 1:
                
                # set delta veriables
                self.delta = self.model.addVars(CompareHouses,vtype = GRB.BINARY,name = "delta") 
                
                # set constraint for delta to make 
                # delta_ij == 1 iff (1-x_i)*(1-x_j)=1 for all pairs (i,j) 
                #                   where i in Occupied houses Set, j in Vacant houses Set
                detlatConstraint1 = self.model.addConstrs((self.x[CompareHouses[i][0]]  + self.delta[CompareHouses[i]] <= 1 
                                      for i in xrange(len(CompareHouses))
                                     ),name = "detlatConstraint1")
                detlatConstraint2 = self.model.addConstrs((self.x[CompareHouses[i][1]]  + self.delta[CompareHouses[i]] <= 1 
                                      for i in xrange(len(CompareHouses))
                                     ),name = "detlatConstraint2")
                detlatConstraint3 = self.model.addConstrs(( -self.x[CompareHouses[i][1]]-self.x[CompareHouses[i][0]]  
                                                     - self.delta[CompareHouses[i]] <= -1 
                                      for i in xrange(len(CompareHouses))
                                     ),name = "detlatConstraint3")
                
                
                # set objective function
                if not Max:
                    # if the gall if minimizing the objective function
                    self.model.setObjective( quicksum(h(self.gdf['centroid'][pare[0]].coords[0],self.gdf['centroid']
                                            [pare[1]].coords[0],d_e,power)*self.delta[pare] for pare in CompareHouses) 
                                            ,GRB.MINIMIZE)
                else:
                    # o.w. maximize
                    self.model.setObjective( quicksum(h(self.gdf['centroid'][pare[0]].coords[0],self.gdf['centroid']
                                            [pare[1]].coords[0],d_e,power)*self.delta[pare] for pare in CompareHouses) 
                                            ,GRB.MAXIMIZE)
            
            
            # use Big M method to replace the original delta method
            # create new varialbe corresponding to the Occupied houses Set
            # Worst Case : O(n) Space
            elif model == 2:
                
                # [ to be improve ] not neccessary need this 10/25
                #occupied = [item[0] for item in CompareHouses]
                #occupied = np.unique(occupied)
                
                # set bigM variable for each occupied houses
                self.bigM = self.model.addVars(occupied,vtype = GRB.CONTINUOUS,name = "bigM",lb = -GRB.INFINITY, ub = 0.0)
                
                
                # set constrain for bigM variables
                test_count = 0
                for o in occupied:
                    
                    # normal by total
                    total = sum( h(self.gdf['centroid'][o].coords[0]
                                           ,self.gdf['centroid'][v].coords[0],d_e,power) for v in vacant)
                    devide = 1.0 if total == 0 else total
                    
                    self.model.addConstr(( self.bigM[o] <= quicksum(h(self.gdf['centroid'][o].coords[0]
                                                        ,self.gdf['centroid'][v].coords[0],d_e,power)*(self.x[v]-1) 
                                                                    for v in vacant)
                                          + 
                                            total*self.x[o] ) , 
                                    name = "for each occupied")
                    
                # set objective function
                # notice that for each bigM constraint 
                # the maximization will be 0 which means there is no any effect on the occupied house
                self.model.setObjective( quicksum(self.bigM[i] for i in occupied), GRB.MAXIMIZE)
            
            
            
            # same as model 2
            # but the distance function is walking distance
            # get the walking distance from openstreetmap 
            # there is some calling limitation issue here
            elif model == 3:
                # [ to be improve ] not neccessary need this 10/25
                #occupied = [item[0] for item in CompareHouses]
                #occupied = np.unique(occupied)
                self.bigM = self.model.addVars(occupied,vtype = GRB.CONTINUOUS,name = "bigM",lb = -GRB.INFINITY, ub = 0.0)
                
                
                for o in occupied:
                    
                    self.model.addConstr(( self.bigM[o] <= quicksum(
                        h(d_e = d_e,power = power,
                          gdf1 = self.gdf.loc[[o]], gdf2 = self.gdf.loc[[v]])*(self.x[v]-1) 
                                                                    for v in vacant) + 
                                            sum(h(d_e = d_e,power = power,
                                                  gdf1 = self.gdf.loc[[o]], 
                                                  gdf2 = self.gdf.loc[[v]]) for v in vacant)*self.x[o] ) , 
                                    name = "for each occupied")
                # set objective function
                # notice that for each bigM constraint 
                # the maximization will be 0 which means there is no any effect on the occupied house
                self.model.setObjective( quicksum(self.bigM[i] for i in occupied), GRB.MAXIMIZE)
                
        
        
        # max(min_{i,j) d_ij) = t_i for each i in occupied houses set
        # the concept kinda like SVM
        # we only care about the closest non-demolished vacant house from the occupied house
        # we want to push it as far as possible by demolish the closest vacant house
        # worst case: O(n) space for new variables
        else:
            
            # set new variable t_i correspond to i-th occupied house
            self.t = self.model.addVars(occupied,vtype = GRB.CONTINUOUS,name = "t")
            
            # set the constraint
            # notive that the distance is geometry_distance here
            for o in occupied:
                
                self.model.addConstrs(( self.t[o] <= d(
                                                       (self.gdf['centroid'][o].coords[0][1],
                                                        self.gdf['centroid'][o].coords[0][0])
                                                      ,(self.gdf['centroid'][v].coords[0][1],
                                                        self.gdf['centroid'][o].coords[0][0])
                                                      )* (1-self.x[v]) + (10000000000)*self.x[v]
                                        for v in vacant
                                      ), name = str(o)+"Constraint"
                                     ) 
                
                self.model.addConstr(( self.t[h] <= 10000000000*(1-self.x[h])), name = str(h))
            
            # set objective function
            self.model.setObjective( quicksum(self.t[i] for i in occupied), GRB.MAXIMIZE)
            
        
    def solve(self):
        """        
        solve the optimzation problem
        """
        self.model.optimize()
        
        # update the status : the max/min of objective functions, and sum of deolished houses set
        self.status_update()
        
        
    def get_x(self):
        """        
        return binary variables
        """
        return self.x
    
    def no_good_update(self):
        
        """        
        add the boundary for current optimal solution
        if the solution set S = { i | x_i == 1 for every i in houses set}
           then for all i in S, set new bound such that
                                                sum_i x_i <= |S|-1
        """
        # 10/26 deal with tolerance
        # check if the solution is non-zero
        if sum(self.x[self.Houses[i]].X for i in xrange(len(self.Houses))) != 0:
            
            self.iter += 1
            self.model.addConstr(
                (
                quicksum(self.x[self.Houses[i]] 
                         if self.x[self.Houses[i]].X == 1 or abs(self.x[self.Houses[i]].X - 1.0) < 0.000001 
                         else 0 for i in xrange(len(self.Houses)))
                <= sum( 1
                       if self.x[self.Houses[i]].X == 1 or abs(self.x[self.Houses[i]].X - 1.0) < 0.000001 
                       else 0 for i in xrange(len(self.Houses)))-1
                ),name = 'temp'
            )

            
    def status_update(self):
        """        
        get the solution detail
            Budget
            number of demolished houses 
            Objective Value
            Running Time
        """
        spent = (sum(self.Cost[i]*self.x[self.Houses[i]].X for i in xrange(len(self.Houses))) +
         sum(self.Wallij[i]*self.z[self.Edge[i]].X for i in xrange(len(self.Edge))) -
         sum(self.Benefit[i]*self.y[self.Edge[i]].X for i in xrange(len(self.Edge))) -
         sum(self.Walli[i]*self.x[self.Edge[i][0]].X for i in xrange(len(self.Edge))) -
         sum(self.Wallj[i]*self.x[self.Edge[i][1]].X for i in xrange(len(self.Edge))) )
        
        num_houses = sum(self.x[self.Houses[i]].X  for i in xrange(len(self.Houses)))
    
        #print "Budget : %s   number of houses : %s" %(spent, num_houses)
        self.status.append("Budget : %s   number of houses : %s   ObjVal : %s   Running Time : %s" %(spent,
                                                                                                     num_houses,
                                                                                                     self.model.ObjVal,
                                                                                                     self.model.Runtime))
    


    
    
    

    
     

        
################################################################################
#
# Distance & Weight Function Collection
#
################################################################################

# initial network map
G = ox.graph_from_address('1516 Kenhill Ave, Baltimore, MD', network_type= 'walk', distance = 1000)
# project the street network to UTM
G_proj = ox.project_graph(G)
nodes = ox.graph_to_gdfs(G, edges=False)


def distance_OSMNX(x,y):
    # x,y - tuples
    # lat1,lng1,lat2,lng2,earth_radius
    # distance or vector of distances from (lat1, lng1) to (lat2, lng2) in units of earth_radius
    # 6371009
    dis = ox.utils.great_circle_vec(x[0],x[1],y[0],y[1])
    return dis
    #return np.sqrt((y[0] - x[0])**2 + (x[1] - y[1])**2)
    
    
def affect_OSMNX(x1=None,x2=None,d_e = 30,power = 1,gdf1 = None, gdf2 = None):

    if x1 != None:
        dis = distance_OSMNX((x1[1],x1[0]),(x2[1],x2[0]))
    elif gdf1 is not None:
        dis = geometry_distance(gdf1,gdf2)
        
    # normailization 1
    #alpha = 1.0/2/math.pi/d_e
    alpha = 1.0
    
    # unit: meter
    return 1.0*alpha/(dis**power) if dis <= d_e else 0


def geometry_distance(gdf1,gdf2):
    
    

    # get_name
    s_name = gdf1['addr:housenumber'][gdf1.index[0]] + " " + gdf1['addr:street'][gdf1.index[0]]\
            + ", " + gdf1['addr:city'][gdf1.index[0]] + ", " +  gdf1['addr:state'][gdf1.index[0]]
    t_name = gdf2['addr:housenumber'][gdf2.index[0]] + " " + gdf2['addr:street'][gdf2.index[0]]\
            + ", " + gdf2['addr:city'][gdf2.index[0]] + ", " +  gdf2['addr:state'][gdf2.index[0]]
        
        
    
    #s = ox.core.graph_from_address(s_name, distance = 100,return_coords=True)[1] # return (lat,log)
    #t = ox.core.graph_from_address(t_name, distance = 100,return_coords=True)[1] # return (lat,log)
    
    s = ox.utils.geocode(s_name) # return (lat,log)
    t = ox.utils.geocode(t_name) # return (lat,log)
    
    
    s_node, s_dis = find_nearest_point(s) # distance in meters
    t_node, t_dis = find_nearest_point(t) # distance in meters
    
    
    
    
    if s_node == t_node:
        print min(s_dis+t_dis, distance_OSMNX(s,t))
        return min(s_dis+t_dis, distance_OSMNX(s,t))
    else:
        # ini
        route_by_length = \
            nx.shortest_path(G_proj, source=s_node, target=t_node, weight='length') # nodes set
        #fig, ax = ox.plot_graph_route(G_proj, route_by_length, node_size=0)
        route_lengths = ox.get_route_edge_attributes(G_proj, route_by_length, 'length') # meters set
        distance = sum(route_lengths) # meter
        
        if distance - s_dis - t_dis > 150:
            return 150
        # s
        else:
            if G[route_by_length[0]][route_by_length[1]][0].get('name') != None and  \
                G[route_by_length[0]][route_by_length[1]][0]['name'] != gdf1['addr:street'][gdf1.index[0]]:
                distance = distance + s_dis
            elif distance_OSMNX(s,(nodes['y'][route_by_length[1]],
                                   nodes['x'][route_by_length[1]])) <= route_lengths[0]:
                distance = distance - s_dis
            else:
                distance = distance + s_dis

            # t
            if G[route_by_length[-1]][route_by_length[-2]][0].get('name') != None and  \
                G[route_by_length[-2]][route_by_length[-1]][0]['name'] != gdf2['addr:street'][gdf2.index[0]]:
                distance = distance + t_dis
            elif distance_OSMNX(t,(nodes['y'][route_by_length[-2]]
                                  ,nodes['x'][route_by_length[1]])) <= route_lengths[-1]:
                distance = distance - t_dis
            else:
                distance = distance + t_dis
            print distance
            return distance#, fig, ax
        
        
    
    
    
def find_nearest_point(node):
    return ox.get_nearest_node(G, node
                             ,method = 'greatcircle' ,return_dist=True
                            )
    
