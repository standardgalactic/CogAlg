# warnings.filterwarnings('error')
# import warnings  # to detect overflow issue, in case of infinity loop
'''
Comp_slice is a terminal fork of intra_blob.
-
In natural images, objects look very fuzzy and frequently interrupted, only vaguely suggested by initial blobs and contours.
Potential object is proximate low-gradient (flat) blobs, with rough / thick boundary of adjacent high-gradient (edge) blobs.
These edge blobs can be dimensionality-reduced to their long axis / median line: an effective outline of adjacent flat blob.
-
Median line can be connected points that are most equidistant from other blob points, but we don't need to define it separately.
An edge is meaningful if blob slices orthogonal to median line form some sort of a pattern: match between slices along the line.
In simplified edge tracing we cross-compare among blob slices in x along y, where y is the longer dimension of a blob / segment.
Resulting patterns effectively vectorize representation: they represent match and change between slice parameters along the blob.
-
This process is very complex, so it must be selective. Selection should be by combined value of gradient deviation of edge blobs
and inverse gradient deviation of flat blobs. But the latter is implicit here: high-gradient areas are usually quite sparse.
A stable combination of a core flat blob with adjacent edge blobs is a potential object.
-
So, comp_slice traces blob axis by cross-comparing vertically adjacent Ps: horizontal slices across an edge blob.
These low-M high-Ma blobs are vectorized into outlines of adjacent flat (high internal match) blobs.
(high match or match of angle: M | Ma, roughly corresponds to low gradient: G | Ga)
-
Vectorization is clustering of parameterized Ps + their derivatives (derPs) into PPs: patterns of Ps that describe edge blob.
This process is a reduced-dimensionality (2D->1D) version of cross-comp and clustering cycle, common across this project.
As we add higher dimensions (3D and time), this dimensionality reduction is done in salient high-aspect blobs
(likely edges in 2D or surfaces in 3D) to form more compressed "skeletal" representations of full-dimensional patterns.
'''
import sys
import numpy as np
from itertools import zip_longest
from copy import deepcopy, copy
from class_cluster import ClusterStructure, NoneType

ave_inv = 20  # ave inverse m, change to Ave from the root intra_blob?
ave = 5  # ave direct m, change to Ave_min from the root intra_blob?
ave_g = 30  # change to Ave from the root intra_blob?
ave_ga = 0.78  # ga at 22.5 degree
flip_ave = .1
flip_ave_FPP = 0  # flip large FPPs only (change to 0 for debug purpose)
div_ave = 200
ave_rmP = .7  # the rate of mP decay per relative dX (x shift) = 1: initial form of distance
ave_ortho = 20
aveB = 50
# comp_param coefs:
ave_dI = ave_inv
ave_M = ave  # replace the rest with coefs:
ave_Ma = 10
ave_G = 10
ave_Ga = 2  # related to dx?
ave_L = 10
ave_x = 1
ave_dx = 5  # inv, difference between median x coords of consecutive Ps
ave_dy = 5
ave_daxis = 2
ave_dangle = 2  # vertical difference between angles
ave_daangle = 2
ave_mval = ave_dval = 10  # should be different
ave_mPP = 10
ave_dPP = 10
ave_splice = 10
ave_nsub = 1
ave_sub = 2  # cost of calling sub_recursion and looping
ave_agg = 3  # cost of agg_recursion
ave_overlap = 10
med_decay = .5
pnames = ["I", "M", "Ma", "axis", "angle", "aangle","G", "Ga", "x", "L"]
aves = [ave_dI, ave_M, ave_Ma, ave_daxis, ave_dangle, ave_daangle, ave_G, ave_Ga, ave_dx, ave_L, ave_mval, ave_dval]
vaves = [ave_mval, ave_dval]
PP_aves = [ave_mPP, ave_dPP]

class Cptuple(ClusterStructure):  # bottom-layer tuple of compared params in P, derH per par in derP, or PP

    I = int  # [m,d] in higher layers:
    M = int
    Ma = float
    axis = lambda: [1, 0]  # ini dy=1,dx=0, old angle after rotation
    angle = lambda: [0, 0]  # in latuple only, replaced by float in vertuple
    aangle = lambda: [0, 0, 0, 0]
    G = float  # for comparison, not summation:
    Ga = float
    x = int  # median: x0+L/2
    L = int  # len dert_ in P, area in PP
    n = lambda: 1  # accum count, combine from CpH?
    valt = lambda: [0,0]
    rdnt = lambda: [1,1]

class CQ(ClusterStructure):  # vertuple, hierarchy, or generic sequence

    Q = list  # generic sequence or index increments in ptuple, derH, etc
    Qm = list  # in-graph only
    Qd = list
    ext = lambda: [[],[]]  # [ms,ds], per subH only
    valt = lambda: [0,0]  # in-graph vals
    rdnt = lambda: [1,1]  # none if represented m and d?
    out_valt = lambda: [0,0]  # of non-graph links, as alt?
    fds = list
    rng = lambda: 1  # is it used anywhere?
    n = int  # accum count in ptuple

class CP(ClusterStructure):  # horizontal blob slice P, with vertical derivatives per param if derP, always positive

    ptuple = object  # latuple: I, M, Ma, G, Ga, angle(Dy, Dx), aangle( Sin_da0, Cos_da0, Sin_da1, Cos_da1), ?[n, val, x, L, A]?
    # replace with derH in sub+
    x0 = int
    y0 = int  # for vertical gap in PP.P__
    dert_ = list  # array of pixel-level derts, redundant to uplink_, only per blob?
    link_ = list  # all links
    link_t = lambda: [[],[]]  # +ve rlink_, dlink_
    roott = lambda: [None,None]  # m,d PP that contain this P
    rdn = int  # blob-level redundancy, ignore for now
    dxdert_ = list  # only in Pd
    Pd_ = list  # only in Pm
    # if comp_dx:
    Mdx = int
    Ddx = int

class CderP(ClusterStructure):  # tuple of derivatives in P link: binary tree with latuple root and vertuple forks

    derH = list  # each layer = [ptuple_,node_,fd], sum links / rng+, layers / der+?
    valt = lambda: [0, 0]  # summed rngQ vals
    rdnt = lambda: [1, 1]  # mrdn + uprdn if branch overlap?
    _P = object  # higher comparand
    P = object  # lower comparand
    roott = lambda: [None,None]  # for der++
    x0 = int
    y0 = int
    L = int
    fdx = NoneType  # if comp_dx
'''
max ntuples / der layer = ntuples in lower layers: 1, 1, 2, 4, 8...
lay1: par     # derH per param in vertuple, each layer is derivatives of all lower layers:
lay2: [m,d]   # implicit nesting, brackets for clarity:
lay3: [[m,d], [md,dd]]: 2 sLays,
lay4: [[m,d], [md,dd], [[md1,dd1],[mdd,ddd]]]: 3 sLays, <=2 ssLays:
'''

class CPP(CderP):  # derP params include P.ptuple

    derH = list  # layer = [ptuple_,node_,fd], += link/rng+| lay/der+? 1st plevel, zipped with alt_derH in comp_derH
    valt = lambda: [0,0]
    rdnt = lambda: [1,1]  # recursion count + Rdn / nderPs + mrdn + uprdn if branch overlap?
    Rdn = int  # for accumulation only?
    rng = lambda: 1
    alt_rdn = int  # overlapping redundancy between core and edge
    alt_PP_ = list  # adjacent alt-fork PPs per PP, from P.roott[1] in sum2PP
    altuple = list  # summed from alt_PP_, sub comp support, agg comp suppression?
    box = lambda: [0,0,0,0]  # y0,yn, x0,xn
    fPPm = NoneType  # PPm if 1, else PPd; not needed if packed in PP_
    fdiv = NoneType
    mask__ = bool
    link__ = list  # combined P link_t[fd] s, may overlap between Ps within line
    nlink__ = list  # miss links, add with nvalt for complemented PP?
    nval = int
    P_cnt = int  # len 2D derP__ in levels[0][fPd]?  ly = len(derP__), also x, y?
    derP_cnt = int  # redundant per P
    P__ = list  # input + derPs, derH[0][1]?
    roott = lambda: [None,None]  # PPPm, PPPd that contain this PP
    cPP_ = list  # rdn reps in other PPPs, to eval and remove


def comp_slice_root(blob, verbose=False):  # always angle blob, composite dert core param is v_g + iv_ga

    from sub_recursion import sub_recursion_eval, rotate_P_, agg_recursion_eval

    P__ = slice_blob(blob, verbose=verbose)  # form 2D array of Ps: blob slices in dert__
    # rotate each P to align it with the direction of P gradient:
    rotate_P_(P__, blob.dert__, blob.mask__)  # rotated Ps are sparse or overlap via redundant derPs, results are not biased?
    # scan rows top-down, comp y-adjacent, x-overlapping Ps, form derP__:
    _P_ = P__[0]  # higher row
    for P_ in P__[1:]:  # lower row
        for P in P_:
            for _P in _P_:  # test for x overlap(_P,P) in 8 directions, derts are positive in all Ps:
                _L = len(_P.dert_); L = len(P.dert_)
                if (P.x0 - 1 < _P.x0 + _L) and (P.x0 + L > _P.x0):
                    vertuple = comp_ptuple(_P.ptuple, P.ptuple); valt = copy(vertuple.valt); rdnt = copy(vertuple.rdnt)
                    derP = CderP(derH=[[[vertuple],[[_P],[P]],0]], valt=valt, rdnt=rdnt, P=P, _P=_P, x0=_P.x0, y0=_P.y0, L=len(_P.dert_))
                    P.link_+=[derP]  # all links
                    if valt[0] > aveB*rdnt[0]: P.link_t[0] += [derP]  # +ve links, fork overlap?
                    if valt[1] > aveB*rdnt[1]: P.link_t[1] += [derP]
                elif (P.x0 + L) < _P.x0:
                    break  # no xn overlap, stop scanning lower P_
        _P_ = P_
    PPm_,PPd_ = form_PP_t(P__, base_rdn=2)
    blob.PPm_, blob.PPd_ = PPm_, PPd_
    blob.derH = [[[], [PPm_,PPd_], [0,1]]]  # special case for blob, pack node_t and fd_t
    # re comp, cluster:
    sub_recursion_eval(blob)  # intra PP, add rlayers, dlayers, seg_levels to select PPs, sum M,G
    # pending update
    # agg_recursion_eval(blob, [copy(blob.PPm_), copy(blob.PPd_)])  # cross PP, Cgraph conversion doesn't replace PPs?


def slice_blob(blob, verbose=False):  # form blob slices nearest to slice Ga: Ps, ~1D Ps, in select smooth edge (high G, low Ga) blobs

    mask__ = blob.mask__  # same as positive sign here
    dert__ = zip(*blob.dert__)  # convert 10-tuple of 2D arrays into 1D array of 10-tuple blob rows
    dert__ = [zip(*dert_) for dert_ in dert__]  # convert 1D array of 10-tuple rows into 2D array of 10-tuples per blob
    P__ = []
    height, width = mask__.shape
    if verbose: print("Converting to image...")

    for y, (dert_, mask_) in enumerate(zip(dert__, mask__)):  # unpack lines, each may have multiple slices -> Ps:
        P_ = []
        _mask = True  # mask the cell before 1st dert
        for x, (dert, mask) in enumerate(zip(dert_, mask_)):
            if verbose: print(f"\rProcessing line {y + 1}/{height}, ", end=""); sys.stdout.flush()

            g, ga, ri, dy, dx, sin_da0, cos_da0, sin_da1, cos_da1 = dert[1:]  # skip i
            if not mask:  # masks: if 0,_1: P initialization, if 0,_0: P accumulation, if 1,_0: P termination
                if _mask:  # ini P params with first unmasked dert
                    Pdert_ = [dert]
                    params = Cptuple(M=ave_g-g,Ma=ave_ga-ga,I=ri, angle=[dy,dx], aangle=[sin_da0, cos_da0, sin_da1, cos_da1])
                else:
                    # dert and _dert are not masked, accumulate P params:
                    params.M+=ave_g-g; params.Ma+=ave_ga-ga; params.I+=ri; params.angle[0]+=dy; params.angle[1]+=dx
                    params.aangle = [_par+par for _par,par in zip(params.aangle, [sin_da0, cos_da0, sin_da1, cos_da1])]
                    Pdert_ += [dert]
            elif not _mask:
                # _dert is not masked, dert is masked, terminate P:
                params.G = np.hypot(*params.angle)  # Dy,Dx  # recompute G,Ga, it can't reconstruct M,Ma
                params.Ga = (params.aangle[1]+1) + (params.aangle[3]+1)  # Cos_da0, Cos_da1
                L = len(Pdert_)
                params.L = L; params.x = x-L/2; params.valt = [params.M+params.Ma, params.G+params.Ga]
                P_+=[CP(ptuple=params, x0=x-(L-1), y0=y, dert_=Pdert_)]
            _mask = mask
        # pack last P, same as above:
        if not _mask:
            params.G = np.hypot(*params.angle); params.Ga = (params.aangle[1]+1) + (params.aangle[3]+1)
            L = len(Pdert_); params.L = L; params.x = x-L/2; params.valt=[params.M+params.Ma,params.G+params.Ga]
            P_ += [CP(ptuple=params, x0=x-(L-1), y0=y, dert_=Pdert_)]
        P__ += [P_]

    blob.P__ = P__
    return P__

def form_PP_t(P__, base_rdn):  # form PPs of derP.valt[fd] + connected Ps'val

    PP_t = []
    for fd in 0, 1:
        fork_P__ = ([copy(P_) for P_ in reversed(P__)])  # scan bottom-up
        PP_ = []; packed_P_ = []  # form initial sequence-PPs:
        for P_ in fork_P__:
            for P in P_:
                if P not in packed_P_:
                    qPP = [[[P]], P.ptuple.valt[fd]]  # init PP is 2D queue of node Ps and sum([P.val+P.link_val])
                    uplink_ = P.link_t[fd]; uuplink_ = []  # next-line links for recursive search
                    while uplink_:
                        for derP in uplink_:
                            if derP._P not in packed_P_:
                                qPP[0].insert(0, [derP._P])  # pack top down
                                qPP[1] += derP.valt[fd]
                                packed_P_ += [derP._P]
                                uuplink_ += derP._P.link_t[fd]
                        uplink_ = uuplink_
                        uuplink_ = []
                    PP_ += [qPP + [ave+1]]  # + [ini reval]
        # prune qPPs by med links val:
        rePP_ = reval_PP_(PP_, fd)  # each PP = [qPP, val, reval]
        PP_t += [[sum2PP(PP, base_rdn, fd) for PP in rePP_]]  # CPP_, may be empty

    return PP_t  # add_alt_PPs_(graph_t)?

def reval_PP_(PP_, fd):  # recursive eval Ps for rePP, prune weakly connected Ps

    rePP_ = []
    while PP_:  # init P__
        P__, val, reval = PP_.pop(0)
        if val > ave:
            if reval < ave:  # same graph, skip re-evaluation:
                rePP_ += [[P__,val,0]]  # reval=0
            else:
                rePP = reval_P_(P__, fd)  # recursive node and link revaluation by med val
                if rePP[1] > ave:  # min adjusted val
                    rePP_ += [rePP]
    if rePP_ and max([rePP[2] for rePP in rePP_]) > ave:  # recursion if any min reval:
        rePP_ = reval_PP_(rePP_, fd)

    return rePP_

def reval_P_(P__, fd):  # prune qPP by (link_ + mediated link__) val

    reval = 0  # recursion value
    Val, prune_ = 0, []   # Val = reval from P links only
    for P_ in P__:
        for P in P_:
            P_val = 0; remove_ = []
            for link in P.link_t[fd]:
                # recursive mediated link layers eval-> med_valH:
                _,_,med_valH = med_eval(link._P.link_t[fd], old_link_=[], med_valH=[], fd=fd)
                # link val + mlinks val + Mlinks val:
                link_val = link.valt[fd] + sum([mlink.valt[fd] for mlink in link._P.link_t[fd]])*med_decay + sum(med_valH)
                if link_val < vaves[fd]:
                    remove_+= [link]; reval += link_val
                else: P_val += link_val
            for link in remove_:
                P.link_t[fd].remove(link)  # prune weak links
            if P_val < vaves[fd]:
                prune_ += [P]
            else:
                Val += P_val  # add comb links val to P

    for P in prune_:
        for link in P.link_t[fd]:  # prune direct links only?
            _P = link._P
            _link_ = _P.link_t[fd]
            if link in _link_:
                _link_.remove(link); reval += link.valt[fd]

    if reval > aveB:
        P__,Val,reval = reval_P_(P__, fd)  # recursion
    return [P__, Val, reval]

def med_eval(last_link_, old_link_, med_valH, fd):  # compute med_valH

    curr_link_ = []; med_val = 0

    for llink in last_link_:
        for _link in llink._P.link_t[fd]:
            if _link not in old_link_: # not-circular link
                old_link_ += [_link]   # evaluated mediated links
                curr_link_ += [_link]  # current link layer,-> last_link_ in recursion
                med_val += _link.valt[fd]
    med_val *= med_decay ** (len(med_valH) + 1)
    med_valH += [med_val]
    if med_val > aveB:
        # last med layer val -> likely next med layer val
        curr_link_, old_link_, med_valH = med_eval(curr_link_, old_link_, med_valH, fd)  # eval next med layer

    return curr_link_, old_link_, med_valH

# not fully updated
def sum2PP(qPP, base_rdn, fd):  # sum PP_segs into PP

    P__, val, _ = qPP
    # init:
    P = P__[0][0]
    if P.link_t[fd]:
        derP = P.link_t[fd][0]
        derH = [[deepcopy(derP.derH[0][0]), copy(derP.derH[0][1]), fd]]
        if len(P.link_t[fd]) > 1: sum_links(derH, P.link_t[fd][1:], fd)
    else: derH = []
    PP = CPP(derH=[[[P.ptuple], [[P]],fd]], box=[P.y0, P__[-1][0].y0, P.x0, P.x0 + len(P.dert_)], rdn=base_rdn, link__=[[copy(P.link_t[fd])]])
    PP.valt[fd] = val
    PP.rdnt[fd] += base_rdn
    PP.nlink__ += [[nlink for nlink in P.link_ if nlink not in P.link_t[fd]]]
    # accum:
    for i, P_ in enumerate(P__):  # top-down
        P_ = []
        for j, P in enumerate(P_):
            P.roott[fd] = PP
            if i or j:  # not init
                sum_ptuple_(PP.derH[0][0], P.ptuple if isinstance(P.ptuple, list) else [P.ptuple])
                P_ += [P]
                if derH: sum_links(PP, derH, P.link_t[fd], fd)  # sum links into new layer
                PP.link__ += [[P.link_t[fd]]]  # pack top down
                # the links may overlap between Ps of the same row?
                PP.nlink__ += [[nlink for nlink in P.link_ if nlink not in P.link_t[fd]]]
                PP.box[0] = min(PP.box[0], P.y0)  # y0
                PP.box[2] = min(PP.box[2], P.x0)  # x0
                PP.box[3] = max(PP.box[3], P.x0 + len(P.dert_))  # xn
        PP.derH[0][0] += [P_]  # pack new P top down
    PP.derH += derH
    return PP

# not fully updated:
def sum_links(DerH, P, fd, fneg=0):

    for derP in P.link_t[fd]:
        derH = derP.derH
        for H, h in zip_longest(DerH, derH, fillvalue=[]):  # each H is [ptuple_, node_, fd]
            if h:
                if H:
                    sum_ptuple_(H[0], h[0], fneg)  # H[0] is ptuple_, sum ptuples
                    for node_ in h[1]:  # H[1] is node__, pack node__
                        H[1] += [node_]
                else:
                    DerH += [[deepcopy(h[0]), copy(h[1]), h[2]]]  # ptuple_,node_,fd (deepcopy node_ causes endless recursion)



def sum_ptuple_(Ptuple_, ptuple_, fneg=0):  # same fds from comp_derH

    for Vertuple, vertuple in zip_longest(Ptuple_, ptuple_, fillvalue=[]):  # H[0] is ptuple_
        if vertuple:
            if Vertuple:
                if isinstance(vertuple, CQ):
                    sum_vertuple(Vertuple, vertuple, fneg)
                else:
                    sum_ptuple(Vertuple, vertuple, fneg)
            elif not fneg:
                Ptuple_ += [deepcopy(vertuple)]


def sum_vertuple(Vertuple, vertuple, fneg=0):

    for i, (m, d) in enumerate(zip(vertuple.Qm, vertuple.Qd)):
        Vertuple.Qm[i] += -m if fneg else m
        Vertuple.Qd[i] += -d if fneg else d
    for i in 0,1:
        Vertuple.valt[i] += vertuple.valt[i]
        Vertuple.rdnt[i] += vertuple.rdnt[i]
    Vertuple.n += 1

def sum_ptuple(Ptuple, ptuple, fneg=0):

    for pname, ave in zip(pnames, aves):
        Par = getattr(Ptuple, pname); par = getattr(ptuple, pname)
        if isinstance(Par, list):  # angle or aangle
            for j, (P,p) in enumerate(zip(Par,par)): Par[j] = P-p if fneg else P+p
        else:
            Par += (-par if fneg else par)
        setattr(Ptuple, pname, Par)

    Ptuple.valt[0] += ptuple.valt[0]; Ptuple.valt[1] += ptuple.valt[1]
    Ptuple.n += 1

def comp_vertuple(_vertuple, vertuple):

    dtuple=CQ(n=_vertuple.n, Q=copy(_vertuple.Q))  # no selection here
    rn = _vertuple.n/vertuple.n  # normalize param as param*rn for n-invariant ratio: _param/ param*rn = (_param/_n)/(param/n)

    for _par, par, ave in zip(_vertuple.Qd, vertuple.Qd, aves):

        m,d = comp_par(_par[1], par[1]*rn, ave)
        dtuple.Qm+=[m]; dtuple.Qd+=[d]; dtuple.valt[0]+=m; dtuple.valt[1]+=d

    return dtuple

def comp_ptuple(_ptuple, ptuple):

    dtuple = CQ(n=_ptuple.n, Q=[0 for par in pnames])
    rn = _ptuple.n / ptuple.n  # normalize param as param*rn for n-invariant ratio: _param / param*rn = (_param/_n) / (param/n)

    for pname, ave in zip(pnames, aves):
        _par = getattr(_ptuple, pname)
        par = getattr(ptuple, pname)
        if pname=="aangle": m,d = comp_aangle(_par, par)
        elif pname in ("axis","angle"): m,d = comp_angle(_par, par)
        else:
            if pname!="x": par*=rn  # normalize by relative accum count
            if pname=="x" or pname=="I": finv = 1
            else: finv=0
            m,d = comp_par(_par, par, ave, finv)

        dtuple.Qm += [m]; dtuple.Qd += [d]; dtuple.valt[0] += m; dtuple.valt[1] += d

    return dtuple

def comp_par(_param, param, ave, finv=0):  # comparand is always par or d in [m,d]

    d = _param - param
    if finv: m = ave - abs(d)  # inverse match for primary params, no mag/value correlation
    else:    m = min(_param, param) - ave
    return [m,d]

def comp_angle(_angle, angle):  # rn doesn't matter for angles

    _Dy, _Dx = _angle
    Dy, Dx = angle
    _G = np.hypot(_Dy,_Dx); G = np.hypot(Dy,Dx)
    sin = Dy / (.1 if G == 0 else G);     cos = Dx / (.1 if G == 0 else G)
    _sin = _Dy / (.1 if _G == 0 else _G); _cos = _Dx / (.1 if _G == 0 else _G)
    sin_da = (cos * _sin) - (sin * _cos)  # sin(α - β) = sin α cos β - cos α sin β
    cos_da = (cos * _cos) + (sin * _sin)  # cos(α - β) = cos α cos β + sin α sin β

    dangle = np.arctan2(sin_da, cos_da)  # scalar, vertical difference between angles
    mangle = ave_dangle - abs(dangle)  # inverse match, not redundant as summed across sign

    return [mangle, dangle]

def comp_aangle(_aangle, aangle):

    _sin_da0, _cos_da0, _sin_da1, _cos_da1 = _aangle
    sin_da0, cos_da0, sin_da1, cos_da1 = aangle

    sin_dda0 = (cos_da0 * _sin_da0) - (sin_da0 * _cos_da0)
    cos_dda0 = (cos_da0 * _cos_da0) + (sin_da0 * _sin_da0)
    sin_dda1 = (cos_da1 * _sin_da1) - (sin_da1 * _cos_da1)
    cos_dda1 = (cos_da1 * _cos_da1) + (sin_da1 * _sin_da1)
    # for 2D, not reduction to 1D:
    # aaangle = (sin_dda0, cos_dda0, sin_dda1, cos_dda1)
    # day = [-sin_dda0 - sin_dda1, cos_dda0 + cos_dda1]
    # dax = [-sin_dda0 + sin_dda1, cos_dda0 + cos_dda1]
    gay = np.arctan2((-sin_dda0 - sin_dda1), (cos_dda0 + cos_dda1))  # gradient of angle in y?
    gax = np.arctan2((-sin_dda0 + sin_dda1), (cos_dda0 + cos_dda1))  # gradient of angle in x?

    daangle = np.arctan2(gay, gax)  # diff between aangles, probably wrong
    maangle = ave_daangle - abs(daangle)  # inverse match, not redundant as summed

    return [maangle,daangle]