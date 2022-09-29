import sys
import numpy as np
from itertools import zip_longest
from copy import deepcopy, copy
from class_cluster import ClusterStructure, NoneType, comp_param, Cdert
import math as math
from comp_slice import *

'''
Blob edges may be represented by higher-composition patterns, etc., if top param-layer match,
in combination with spliced lower-composition patterns, etc, if only lower param-layers match.
This may form closed edge patterns around flat core blobs, which defines stable objects.   
'''

ave_G = 6  # fixed costs per G
ave_Gm = 5  # for inclusion in graph
ave_Gd = 4
G_aves = [ave_Gm, ave_Gd]
ave_med = 3  # call cluster_node_layer
ave_rng = 3  # rng per combined val


class Cgraph(CPP):  # graph or generic PP of any composition

    plevels = list  # max n ptuples / level = n ptuples in all lower layers: 1, 1, 2, 4, 8...
    # plevel_t[1]s from alt-fork graphs, sub comp support, agg comp suppression?
    fds = list  # prior forks in plevels, then player fds in plevel
    valt = lambda: [0, 0]  # mval, dval from cis+alt forks
    nvalt = lambda: [0, 0]  # from neg open links
    rdn = int  # for PP evaluation, recursion count + Rdn / nderPs; no alt_rdn: valt representation in alt_PP_ valts?
    rng = lambda: 1  # rng starts with 1, not for alt_PPs
    box = list
    link_ = list  # all evaluated external graph links, nested in link_layers? open links replace alt_node_
    node_ = list  # graph elements, root of layers and levels:
    rlayers = list  # | mlayers, top-down
    dlayers = list  # | alayers
    mlevels = list  # agg_PPs ) agg_PPPs ) agg_PPPPs.., bottom-up
    dlevels = list
    roott = lambda: [None, None]  # higher-order segG or graph
    # cG_ = list  # co-refs in other graphs


def agg_recursion(root, G_, fseg):  # compositional recursion in root.PP_, pretty sure we still need fseg, process should be different

    ivalt = root.valt
    mgraph_, dgraph_ = form_graph_(root, G_)  # PP cross-comp and clustering

    # intra graph:
    if root.valt[0] > ave_sub * root.rdn:
        sub_rlayers, rvalt = sub_recursion_g(mgraph_, root.valt, fd=0)  # subdivide graph.node_ by der+|rng+, accum root.valt
        root.valt[0] += sum(rvalt); root.rlayers = sub_rlayers
    if root.valt[1] > ave_sub * root.rdn:
        sub_dlayers, dvalt = sub_recursion_g(dgraph_, root.valt, fd=1)
        root.valt[1] += sum(dvalt); root.dlayers = sub_dlayers

    # cross graph:
    root.mlevels += mgraph_; root.dlevels += dgraph_
    for fd, graph_ in enumerate([mgraph_, dgraph_]):
        adj_val = root.valt[fd] - ivalt[fd]
        # recursion if adjusted val:
        if (adj_val > G_aves[fd] * ave_agg * (root.rdn + 1)) and len(graph_) > ave_nsub:
            root.rdn += 1  # estimate
            agg_recursion(root, graph_, fseg=fseg)  # cross-comp graphs


def form_graph_(root, G_):  # G is potential node graph, in higher-order GG graph

    for G in G_:  # initialize mgraph, dgraph as roott per G, for comp_G_
        for i in 0,1:
            graph = [[G],[0,0]]  # proto GG: [node_, valt]
            G.roott[i] = graph

    comp_G_(G_)  # cross-comp all PPs within rng, PPs may be segs
    mgraph_, dgraph_ = [],[]  # initialize graphs with >0 positive links in PP roots:
    for G in G_:
        if len(G.roott[0][0])>1: mgraph_ += [G.roott[0]]  # root = [node_, valt] for cluster_node_layer eval, + link_nvalt?
        if len(G.roott[1][0])>1: dgraph_ += [G.roott[1]]

    for fd, graph_ in enumerate([mgraph_, dgraph_]):  # evaluate intermediate nodes to delete or merge graphs:
        regraph_ = []
        while graph_:
            graph = graph_.pop(0)
            med_node__ = [[derG.node_[1] if derG.node_[0] is G else derG.node_[0] for derG in G.link_] for G in graph[0]]
            cluster_node_layer(graph_= graph_, graph=graph, med_node__= med_node__, fd=fd)
            if graph[1][fd] > ave_agg: regraph_ += [graph]  # graph reformed by merges and removes in cluster_node_layer

        if regraph_:
            graph_[:] = sum2graph_(regraph_, fd)  # sum proto-graph node_ params in graph
            plevels = deepcopy(graph_[0].plevels)
            for graph in graph_[1:]:
                sum_plevel_ts(plevels, graph.plevels)  # accum root plevels, each is plevel_t: plevel, alt_plevel
            root.plevels = plevels

    return mgraph_, dgraph_


def comp_G_(G_):  # cross-comp Gs (patterns of patterns): Gs, derGs, or segs inside PP

    for i, _G in enumerate(G_):  # compare _G to other Gs in rng, bilateral link assign:
        for G in G_[i+1:]:

            area = G.plevels[0][G.fds[-1]][0][0][0].L; _area = _G.plevels[0][_G.fds[-1]][0][0][0].L
            # not revised: 1st plevel_t' fork' players' 1st player' 1st ptuple' L
            dx = ((_G.xn - _G.x0) / 2) / _area - ((G.xn - G.x0) / 2) / area
            dy = _G.y / _area - G.y / area
            distance = np.hypot(dy, dx)  # Euclidean distance between PP centroids
            if distance <= ave_rng * ((sum(_G.valt)+sum(G.valt)) / (2*sum(G_aves))):  # max distance depends on combined val

                mplevel_t, dplevel_t, mvalt, dvalt = comp_plevel_ts(_G.plevels, G.plevels)
                valt = [sum(mvalt) - ave_Gm, sum(dvalt) - ave_Gd]  # *= link rdn?
                plevel_t = [[mplevel_t,[],mvalt], [dplevel_t,[],dvalt]]
                derG = Cgraph(plevels=[plevel_t], fds=[0], val_t=valt, node_=[_G, G])

                # any val:
                _G.link_ += [derG]; G.link_ += [derG]
                for fd in 0,1:
                    if valt[fd] > 0:  # no alt fork support?
                        for node, (graph, gvalt) in zip([_G, G], [G.roott[fd], _G.roott[fd]]):  # bilateral inclusion
                            if node not in graph:
                                graph += [node]
                                gvalt[0] += node.valt[0]; gvalt[1] += node.valt[1]


def cluster_node_layer(graph_, graph, med_node__, fd):  # recursive eval of mutual links in increasingly mediated nodes

    node_, valt = graph
    save_node_, save_med__ = [],[]  # __Gs that mediate between Gs and _Gs
    adj_Val = 0

    for G, med_node_ in zip(node_, med_node__):
        save_med_ = []
        for _G in med_node_:
            for derG in _G.link_:
                if derG not in G.link_:  # link_ includes all unique evaluated mediated links, flat or in layers?
                    # med_PP.link_:
                    med_link_ = derG.node_[0].link_ if derG.node_[0] is not _G else derG.node_[1].link_
                    for _derG in med_link_:
                        if G in _derG.node_ and _derG not in G.link_:  # __G mediates between _G and G
                            G.link_ += [_derG]
                            adj_val = _derG.valt[fd] - ave_agg  # or increase ave per mediation depth
                            # adjust nodes:
                            G.valt[fd] += adj_val; _G.valt[fd] += adj_val
                            valt[fd] += adj_val; _G.roott[fd][0][fd] += adj_val  # root is not graph yet
                            # or batch recompute?
                            __G = _derG.node_[0] if _derG.node_[0] is not _G else _derG.node_[1]
                            if __G not in save_med_:  # if not saved via prior _PP
                                save_med_ += [__G]
                                adj_Val += adj_val  # save_med__ val?
        if G.valt[fd]>0:
            # G remains in graph
            save_node_ += [G]; save_med__ += [save_med_]  # save_med__ is nested, may be empty

    add_node_, add_med__ = [], []  # eval graph after adjustment by mediating node layer:
    for G, _G_ in zip(save_node_, save_med__):
        for _G in _G_:
            _graph = _G.roott[fd]
            if _graph in graph_ and _graph is not graph:  # was not removed or merged via prior _G
                _node_, _valt = _graph
                for _node in _node_:  # merge graphs, add direct links:
                    add_node_ += [_node]
                    add_med__.append([derG.node_[1] if derG.node_[0] is _node else derG.node_[0] for derG in _node.link_])
                valt[fd] += _valt[fd]
                graph_.remove(_graph)

    if valt[fd] > ave_G:  # adjusted graph value
        node_[:] = save_node_ + add_node_  # reassign as save_node_ (>0 after mediation) + add_node_ (mediated positive link nodes)
        med_node__[:] = save_med__ + add_med__
        if adj_Val > ave_med:
            # and med_node__?
            # eval next mediation layer in reformed graph:
            cluster_node_layer(graph_, graph, med_node__, fd)


def sub_recursion_g(graph_, fseg, fd):  # rng+: extend G_ per graph, der+: replace G_ with derG_

    comb_layers_t = [[],[]]
    sub_valt = [0,0]
    for graph in graph_:
        if fd:
            node_ = []  # positive links within graph
            for node in graph.node_:
                for link in node.link_:
                    if link.valt[0]>0 and link not in node_:
                        node_ += [link]
        else: node_ = graph.node_

        if graph.valt[fd] > G_aves[fd] and len(node_) > ave_nsub:
            sub_mgraph_, sub_dgraph_ = form_graph_(graph, node_)  # cross-comp and clustering cycle

            if graph.valt[0] > ave_sub * graph.rdn:  # rng +:
                sub_rlayers, valt = sub_recursion_g(sub_mgraph_, graph.valt, fd=0)
                rvalt = sum(valt); graph.valt[0] += rvalt; sub_valt[0] += rvalt  # not sure
                graph.rlayers = [sub_mgraph_] + [sub_rlayers]
            # if > cost of calling sub_recursion and looping:
            if graph.valt[1] > ave_sub * graph.rdn:  # der+:
                sub_dlayers, valt = sub_recursion_g(sub_dgraph_, graph.valt, fd=1)
                dvalt = sum(valt); graph.valt[1] += dvalt; sub_valt[1] += dvalt
                graph.dlayers = [sub_dgraph_] + [sub_dlayers]

            for comb_layers, graph_layers in zip(comb_layers_t, [graph.rlayers, graph.dlayers]):
                for i, (comb_layer, graph_layer) in enumerate(zip_longest(comb_layers, graph_layers, fillvalue=[])):
                    if graph_layer:
                        if i > len(comb_layers) - 1:
                            comb_layers += [graph_layer]  # add new r|d layer
                        else:
                            comb_layers[i] += graph_layer  # splice r|d PP layer into existing layer

    return comb_layers_t, sub_valt


def sum2graph_(G_, fd):  # sum node and link params into graph

    graph_ = []  # new graph_
    for G in G_:
        node_, valt = G
        link_ = []  # to avoid rdn
        graph = Cgraph(node_=node_, plevels=[[]], fds=deepcopy(node_[0].fds), x0=node_[0].x0, xn=node_[0].xn, y0=node_[0].y0, yn=node_[0].yn)
        plevel_t, fds, valt = [], [], [0,0]
        for node in node_:
            graph.valt[0] += node.valt[0]; graph.valt[1] += node.valt[1]
            graph.x0=min(graph.x0, node.x0)
            graph.xn=max(graph.xn, node.xn)
            graph.y0=min(graph.y0, node.y0)
            graph.yn=max(graph.yn, node.yn)
            # accum params:
            if not graph.plevels:  # initialization
                graph.plevels = deepcopy(node.plevels)
            else:
                sum_plevel_ts(graph.plevels[:-1], node.plevels)
            # draft:
            for derG in node.link_:  # accum derG in new level
                if derG in link_:
                    continue
                sum_plevel_t(graph.plevels[-1], derG.plevels[0][fd])
                valt[0] += derG.valt[0][fd]; valt[1] += derG.valt[1][fd]
                derG.roott[fd] = graph
                link_ = [derG]  # to avoid rdn
        # update fds
        fds[:] = deepcopy(graph.plevels[-1][1] + [fd])
        graph_ += [graph]

    return graph_


def comp_plevel_ts(_plevels, plevels):

    mplevel_t, dplevel_t = [[],[]], [[],[]]
    mValt, dValt = [0, 0], [0, 0]

    for _plevel_t, plevel_t in zip(_plevels, plevels):
        for alt, (_plevel, plevel) in enumerate(zip(_plevel_t, plevel_t)):
            # cis | alt fork:
            if _plevel and plevel:
                _players, _fds, _valt = _plevel
                players, fds, valt = plevel
                mplayer, dplayer, mval, dval = comp_players(_players, players, _fds, fds)
                mplevel_t[alt] += [mplayer]; dplevel_t[alt] += [dplayer]
                mValt[alt] += mval; dValt[alt] += dval

    return mplevel_t, dplevel_t, mValt, dValt

def comp_plevels(_plevels, plevels, _fds, fds):

    mlevel, dlevel = [], []  # flat lists of ptuples, nesting decoded by mapping to lower levels
    mVal, dVal = 0,0

    for (_plevel, _lfds, _valt), (plevel, lfds, valt), _fd, fd in zip(_plevels, plevels, _fds, fds):
        if _fd==fd:
            mplayer, dplayer, mval, dval = comp_players(_plevel, plevel, _lfds, lfds)
            mlevel += mplayer; mVal += mval
            dlevel += dplayer; dVal += dval
        else:
            break  # only same-fd players are compared

    return mlevel, dlevel, mVal, dVal

def comp_players(_layers, layers, _fds, fds):  # unpack and compare der layers, if any from der+

    mplayer, dplayer = [], []  # flat lists of ptuples, nesting decoded by mapping to lower levels
    mval, dval = 0, 0

    for _player, player, _fd, fd in zip(_layers, layers, _fds, fds):
        if _fd==fd:
            for _ptuple, ptuple in zip(_player, player):
                mtuple, dtuple = comp_ptuple(_ptuple, ptuple)
                mplayer += [mtuple]; mval = mtuple.val
                dplayer += [dtuple]; dval = dtuple.val
        else:
            break  # only same-fd players are compared

    return mplayer, dplayer, mval, dval

# sum multiple plevels_t, and same fds is the summing criteria
def sum_plevel_ts(pLevels, plevels):

    for pLevel_t, plevel_t in zip_longest(pLevels, plevels, fillvalue=[]):
        if plevel_t:  # plevel_t must not be empty list from zip_longest
            if pLevel_t:
                for pLevel, plevel in zip_longest(pLevel_t, plevel_t, fillvalue=[]):
                    # cis | alt forks
                    if plevel and plevel[0]:
                        if pLevel:
                            if pLevel[0]: sum_players(pLevel[0], plevel[0], pLevel[1], plevel[1])  # accum nodes' players
                            else:         pLevel[0] = deepcopy(plevel[0])  # append node's players
                            pLevel[1] = deepcopy(plevel[1])  # assign fds
                            pLevel[2][0] += plevel[2][0]
                            pLevel[2][1] += plevel[2][1]  # accumulate valt
                        else:
                            pLevel.append(deepcopy(plevel))  # pack new plevel
            else:  # pack new plevel_t
                pLevels.append(deepcopy(plevel_t))

# sum single plevel_t, fds is not summing criteria
def sum_plevel_t(pLevel_t, plevel_t):

    for fd, (pLevel, plevel) in enumerate(zip(pLevel_t, plevel_t)):  # each m|d fork
        for pLayer, player in zip_longest(pLevel[0], plevel[0], fillvalue=[]):  # each player in players
            if player:
                if pLayer:
                    sum_player(pLayer,player)
                else:
                    pLevel[0] += [player]  # pack new player

# old
def sum_plevels(pLevels, plevels):

    for pLevel, plevel in zip_longest(pLevels, plevels, fillvalue=[]):
        if plevel and plevel[0]:
            if pLevel:
                if pLevel[0]: sum_players(pLevel[0], plevel[0], pLevel[1], plevel[1])  # accum nodes' players
                else:         pLevel[0] = deepcopy(plevel[0])  # append node's players
                pLevel[1] = deepcopy(plevel[1])  # assign fds
                pLevel[2][0] += plevel[2][0]; pLevel[2][1] += plevel[2][1]  # accumulate valt
            else:
                pLevels.append(deepcopy(plevel))  # pack new plevel

def sum_players(Layers, layers, Fds, fds, fneg=0):  # accum layers while same fds

    fbreak = 0
    for i, (Layer, layer, Fd, fd) in enumerate(zip(Layers, layers, Fds, fds)):
        if Fd==fd:
            sum_player(Layer, layer, fneg=fneg)
        else:
            fbreak = 1
            break
    Fds[:] = Fds[:i+1-fbreak]


# not revised, this is an alternative to form_graph, but may not be accurate enough to cluster:
def comp_centroid(PPP_):  # comp PP to average PP in PPP, sum >ave PPs into new centroid, recursion while update>ave

    update_val = 0  # update val, terminate recursion if low

    for PPP in PPP_:
        PPP_valt = [0 ,0]  # new total, may delete PPP
        PPP_rdn = 0  # rdn of PPs to cPPs in other PPPs
        PPP_players_t = [[], []]
        DerPP = CderG(player=[[], []])  # summed across PP_:
        Valt = [0, 0]  # mval, dval

        for i, (PP, _, fint) in enumerate(PPP.PP_):  # comp PP to PPP centroid, derPP is replaced, use comp_plevels?
            Mplayer, Dplayer = [],[]
            # both PP core and edge are compared to PPP core, results are summed or concatenated:
            for fd in 0, 1:
                if PP.players_t[fd]:  # PP.players_t[1] may be empty
                    mplayer, dplayer = comp_players(PPP.players_t[0], PP.players_t[fd], PPP.fds, PP.fds)  # params norm in comp_ptuple
                    player_t = [Mplayer + mplayer, Dplayer + dplayer]
                    valt = [sum([mtuple.val for mtuple in mplayer]), sum([dtuple.val for dtuple in dplayer])]
                    Valt[0] += valt[0]; Valt[1] += valt[1]  # accumulate mval and dval
                    # accum DerPP:
                    for Ptuple, ptuple in zip_longest(DerPP.player_t[fd], player_t[fd], fillvalue=[]):
                        if ptuple:
                            if not Ptuple: DerPP.player_t[fd].append(ptuple)  # pack new layer
                            else:          sum_players([[Ptuple]], [[ptuple]])
                    DerPP.valt[fd] += valt[fd]

            # compute rdn:
            cPP_ = PP.cPP_  # sort by derPP value:
            cPP_ = sorted(cPP_, key=lambda cPP: sum(cPP[1].valt), reverse=True)
            rdn = 1
            fint = [0, 0]
            for fd in 0, 1:  # sum players per fork
                for (cPP, CderG, cfint) in cPP_:
                    if valt[fd] > PP_aves[fd] and PP.players_t[fd]:
                        fint[fd] = 1  # PPs match, sum derPP in both PPP and _PPP:
                        sum_players(PPP.players_t[fd], PP.players_t[fd])
                        sum_players(PPP.players_t[fd], PP.players_t[fd])  # all PP.players in each PPP.players

                    if CderG.valt[fd] > Valt[fd]:  # cPP is instance of PP
                        if cfint[fd]: PPP_rdn += 1  # n of cPPs redundant to PP, if included and >val
                    else:
                        break  # cPP_ is sorted by value

            fnegm = Valt[0] < PP_aves[0] * rdn;  fnegd = Valt[1] < PP_aves[1] * rdn  # rdn per PP
            for fd, fneg, in zip([0, 1], [fnegm, fnegd]):

                if (fneg and fint[fd]) or (not fneg and not fint[fd]):  # re-clustering: exclude included or include excluded PP
                    PPP.PP_[i][2][fd] = 1 -  PPP.PP_[i][2][fd]  # reverse 1-0 or 0-1
                    update_val += abs(Valt[fd])  # or sum abs mparams?
                if not fneg:
                    PPP_valt[fd] += Valt[fd]
                    PPP_rdn += 1  # not sure
                if fint[fd]:
                    # include PP in PPP:
                    if PPP_players_t[fd]: sum_players(PPP_players_t[fd], PP.players_t[fd])
                    else: PPP_players_t[fd] = copy(PP.players_t[fd])  # initialization is simpler
                    # not revised:
                    PPP.PP_[i][1] = derPP   # no derPP now?
                    for i, cPPt in enumerate(PP.cPP_):
                        cPPP = cPPt[0].root
                        for j, PPt in enumerate(cPPP.cPP_):  # get PPP and replace their derPP
                            if PPt[0] is PP:
                                cPPP.cPP_[j][1] = derPP
                        if cPPt[0] is PP: # replace cPP's derPP
                            PPP.cPP_[i][1] = derPP
                PPP.valt[fd] = PPP_valt[fd]

        if PPP_players_t: PPP.players_t = PPP_players_t

        # not revised:
        if PPP_val < PP_aves[fPd] * PPP_rdn:  # ave rdn-adjusted value per cost of PPP

            update_val += abs(PPP_val)  # or sum abs mparams?
            PPP_.remove(PPP)  # PPPs are hugely redundant, need to be pruned

            for (PP, derPP, fin) in PPP.PP_:  # remove refs to local copy of PP in other PPPs
                for (cPP, _, _) in PP.cPP_:
                    for i, (ccPP, _, _) in enumerate(cPP.cPP_):  # ref of ref
                        if ccPP is PP:
                            cPP.cPP_.pop(i)  # remove ccPP tuple
                            break

    if update_val > sum(PP_aves):
        comp_centroid(PPP_)  # recursion while min update value

    return PPP_
'''
    1st and 2nd layers are single sublayers, the 2nd adds tuple pair nesting. Both are unpacked by func_pairs, not func_layers.  
    Multiple sublayers start on the 3rd layer, because it's derived from comparison between two (not one) lower layers. 
    4th layer is derived from comparison between 3 lower layers, where the 3rd layer is already nested, etc:
    initial 3-layer nesting: https://github.com/assets/52521979/ea6d436a-6c5e-429f-a152-ec89e715ebd6
    '''

# the below is out of date:
# draft, splice 2 PPs for now
def splice_PPs(PP_, frng):  # splice select PP pairs if der+ or triplets if rng+

    spliced_PP_ = []
    while PP_:
        _PP = PP_.pop(0)  # pop PP, so that we can differentiate between tested and untested PPs
        tested_segs = []  # new segs may be added during splicing, their links also need to be checked for splicing
        _segs = _PP.seg_levels[0]

        while _segs:
            _seg = _segs.pop(0)
            _avg_y = sum([P.y for P in _seg.P__]) / len(_seg.P__)  # y centroid for _seg

            for link in _seg.uplink_layers[1] + _seg.downlink_layers[1]:
                seg = link.P.root  # missing link of current seg

                if seg.root is not _PP:  # after merging multiple links may have the same PP
                    avg_y = sum([P.y for P in seg.P__]) / len(seg.P__)  # y centroid for seg

                    # test for y distance (temporary)
                    if (_avg_y - avg_y) < ave_splice:
                        if seg.root in PP_:
                            PP_.remove(seg.root)  # remove merged PP
                        elif seg.root in spliced_PP_:
                            spliced_PP_.remove(seg.root)
                        # splice _seg's PP with seg's PP
                        merge_PP(_PP, seg.root)

            tested_segs += [_seg]  # pack tested _seg
        _PP.seg_levels[0] = tested_segs
        spliced_PP_ += [_PP]

    return spliced_PP_


def merge_PP(_PP, PP, fPd):  # only for PP splicing

    for seg in PP.seg_levels[fPd][-1]:  # merge PP_segs into _PP:
        accum_PP(_PP, seg, fPd)
        _PP.seg_levels[fPd][-1] += [seg]

    # merge uplinks and downlinks
    for uplink in PP.uplink_layers:
        if uplink not in _PP.uplink_layers:
            _PP.uplink_layers += [uplink]
    for downlink in PP.downlink_layers:
        if downlink not in _PP.downlink_layers:
            _PP.down_layers += [downlink]