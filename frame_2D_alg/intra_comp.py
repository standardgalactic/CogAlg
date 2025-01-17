"""
Cross-comparison of pixels or gradient angles in 2x2 kernels
"""

import numpy as np
import functools
# no ave_ga = .78, ave_ma = 2  # at 22.5 degrees
# https://github.com/boris-kz/CogAlg/blob/master/frame_2D_alg/Illustrations/intra_comp_diagrams.png

def comp_r(dert__, rng, mask__=None):
    '''
    Cross-comparison of input param (dert[0]) over rng passed from intra_blob.
    This fork is selective for blobs with below-average gradient in shorter-range cross-comp: input intensity didn't vary much.
    Such input is predictable enough for selective sampling: skipping current rim in following comparison kernels.
    Skipping forms increasingly sparse dert__ for next-range cross-comp,
    hence kernel width increases as 2^rng: 1: 2x2 kernel, 2: 4x4 kernel, 3: 8x8 kernel
    There is also skipping within greater-rng rims, so configuration of compared derts is always 2x2
    '''

    i__ = dert__[0]  # pixel intensity, should be separate from i__sum
    # sparse aligned rim arrays:
    i__topleft = i__[:-1:2, :-1:2]  # also assignment to new_dert__[0]
    i__topright = i__[:-1:2, 1::2]
    i__bottomleft = i__[1::2, :-1:2]
    i__bottomright = i__[1::2, 1::2]
    ''' 
    unmask all derts in kernels with only one masked dert (can be set to any number of masked derts), 
    to avoid extreme blob shrinking and loss of info in other derts of partially masked kernels
    unmasked derts were computed due to extend_dert() in intra_blob   
    '''
    if mask__ is not None:
        majority_mask__ = ( mask__[:-1:2, :-1:2].astype(int)
                          + mask__[:-1:2, 1::2].astype(int)
                          + mask__[1::2, 1::2].astype(int)
                          + mask__[1::2, :-1:2].astype(int)
                          ) > 1
    else:
        majority_mask__ = None  # returned at the end of function

    d_upleft__ = dert__[1][:-1:2, :-1:2].copy()  # sparse step=2 sampling
    d_upright__= dert__[2][:-1:2, :-1:2].copy()
    rngSkip = 1
    if rng>2: rngSkip *= (rng-2)*2  # *2 for 8x8, *4 for 16x16
    # combined distance and extrapolation coeffs, or separate distance coef: ave * (rave / dist), rave = ave abs d / ave i?
    # compare pixels diagonally:
    d_upright__+= (i__bottomleft - i__topright) * rngSkip
    d_upleft__ += (i__bottomright - i__topleft) * rngSkip

    g__ = np.hypot(d_upright__, d_upleft__)  # match = inverse of abs gradient (variation), recomputed at each comp_r
    ri__ = i__topleft + i__topright + i__bottomleft + i__bottomright

    return (i__topleft, d_upleft__, d_upright__, g__, ri__), majority_mask__


def comp_a(dert__, mask__=None):  # cross-comp of gradient angle in 2x2 kernels

    if mask__ is not None:
        majority_mask__ = (mask__[:-1, :-1].astype(int) +
                           mask__[:-1, 1:].astype(int) +
                           mask__[1:, 1:].astype(int) +
                           mask__[1:, :-1].astype(int)
                           ) > 1
    else:
        majority_mask__ = None

    i__, dy__, dx__, g__, ri__ = dert__[:5]  # day__,dax__,ma__ are recomputed

    with np.errstate(divide='ignore', invalid='ignore'):  # suppress numpy RuntimeWarning
        angle__ = [dy__, dx__] / np.hypot(dy__, dx__)
        for angle_ in angle__: angle_[np.where(np.isnan(angle_))] = 0  # set nan to 0, to avoid error later

    # angle__ shifted in 2x2 kernels:
    angle__topleft  = angle__[:, :-1, :-1]  # a is 3 dimensional
    angle__topright = angle__[:, :-1, 1:]
    angle__botright = angle__[:, 1:, 1:]
    angle__botleft  = angle__[:, 1:, :-1]

    sin_da0__, cos_da0__ = angle_diff(angle__botleft, angle__topright)  # dax__ contains 2 component arrays: sin(dax), cos(dax) ...
    sin_da1__, cos_da1__ = angle_diff(angle__botright, angle__topleft)  # ... same for day

    with np.errstate(divide='ignore', invalid='ignore'):  # suppress numpy RuntimeWarning
        ga__ = (cos_da0__ + 1) + (cos_da1__ + 1)  # +1 for all positives
        # or ga__ = np.hypot( np.arctan2(*day__), np.arctan2(*dax__)?

    # angle change in y, sines are sign-reversed because da0 and da1 are top-down, no reversal in cosines
    day__ = [-sin_da0__ - sin_da1__, cos_da0__ + cos_da1__]
    # angle change in x, positive sign is right-to-left, so only sin_da0__ is sign-reversed
    dax__ = [-sin_da0__ + sin_da1__, cos_da0__ + cos_da1__]
    '''
    sin(-θ) = -sin(θ), cos(-θ) = cos(θ): 
    sin(da) = -sin(-da), cos(da) = cos(-da) => (sin(-da), cos(-da)) = (-sin(da), cos(da))
    in conventional notation: G = (Ix, Iy), A = (Ix, Iy) / hypot(G), DA = (dAdx, dAdy), abs_GA = hypot(DA)?
    '''
    i__ = i__[:-1, :-1]
    dy__ = dy__[:-1, :-1]  # passed on as idy, not rotated
    dx__ = dx__[:-1, :-1]  # passed on as idx, not rotated
    g__ = g__[:-1, :-1]
    ri__ = ri__[:-1, :-1]  # for summation in Dert

    return (i__, g__, ga__, ri__, dy__, dx__, day__[0], dax__[0], day__[1], dax__[1]), majority_mask__


def angle_diff(a2, a1):  # compare angle_1 to angle_2 (angle_1 to angle_2)

    sin_1, cos_1 = a1[:]
    sin_2, cos_2 = a2[:]

    # sine and cosine of difference between angles:

    sin_da = (cos_1 * sin_2) - (sin_1 * cos_2)
    cos_da = (cos_1 * cos_2) + (sin_1 * sin_2)

    return [sin_da, cos_da]

'''
alternative versions below:
'''
def comp_r_odd(dert__, ave, rng, root_fia, mask__=None):
    '''
    Cross-comparison of input param (dert[0]) over rng passed from intra_blob.
    This fork is selective for blobs with below-average gradient,
    where input intensity didn't vary much in shorter-range cross-comparison.
    Such input is predictable enough for selective sampling: skipping current
    rim derts as kernel-central derts in following comparison kernels.
    Skipping forms increasingly sparse output dert__ for greater-range cross-comp, hence
    rng (distance between centers of compared derts) increases as 2^n, with n starting at 0:
    rng = 1: 3x3 kernel,
    rng = 2: 5x5 kernel,
    rng = 3: 9x9 kernel,
    ...
    Sobel coefficients to decompose ds into dy and dx:
    YCOEFs = np.array([-1, -2, -1, 0, 1, 2, 1, 0])
    XCOEFs = np.array([-1, 0, 1, 2, 1, 0, -1, -2])
        |--(clockwise)--+  |--(clockwise)--+
        YCOEF: -1  -2  -1  ¦   XCOEF: -1   0   1  ¦
                0       0  ¦          -2       2  ¦
                1   2   1  ¦          -1   0   1  ¦
    Scharr coefs:
    YCOEFs = np.array([-47, -162, -47, 0, 47, 162, 47, 0])
    XCOEFs = np.array([-47, 0, 47, 162, 47, 0, -47, -162])
    Due to skipping, configuration of input derts in next-rng kernel will always be 3x3, using Sobel coeffs, see:
    https://github.com/boris-kz/CogAlg/blob/master/frame_2D_alg/Illustrations/intra_comp_diagrams.png
    https://github.com/boris-kz/CogAlg/blob/master/frame_2D_alg/Illustrations/intra_comp_d.drawio
    '''

    i__ = dert__[0]  # i is pixel intensity

    '''
    sparse aligned i__center and i__rim arrays:
    rotate in first call only: same orientation as from frame_blobs?
    '''
    i__center = i__[1:-1:2, 1:-1:2]  # also assignment to new_dert__[0]
    i__topleft = i__[:-2:2, :-2:2]
    i__top = i__[:-2:2, 1:-1:2]
    i__topright = i__[:-2:2, 2::2]
    i__right = i__[1:-1:2, 2::2]
    i__bottomright = i__[2::2, 2::2]
    i__bottom = i__[2::2, 1:-1:2]
    i__bottomleft = i__[2::2, :-2:2]
    i__left = i__[1:-1:2, :-2:2]
    ''' 
    unmask all derts in kernels with only one masked dert (can be set to any number of masked derts), 
    to avoid extreme blob shrinking and loss of info in other derts of partially masked kernels
    unmasked derts were computed due to extend_dert() in intra_blob   
    '''
    if mask__ is not None:
        majority_mask__ = ( mask__[1:-1:2, 1:-1:2].astype(int)
                          + mask__[:-2:2, :-2:2].astype(int)
                          + mask__[:-2:2, 1:-1: 2].astype(int)
                          + mask__[:-2:2, 2::2].astype(int)
                          + mask__[1:-1:2, 2::2].astype(int)
                          + mask__[2::2, 2::2].astype(int)
                          + mask__[2::2, 1:-1:2].astype(int)
                          + mask__[2::2, :-2:2].astype(int)
                          + mask__[1:-1:2, :-2:2].astype(int)
                          ) > 1
    else:
        majority_mask__ = None  # returned at the end of function
    '''
    can't happen:
    if root_fia:  # initialize derivatives:  
        dy__ = np.zeros_like(i__center)  # sparse to align with i__center
        dx__ = np.zeros_like(dy__)
        m__ = np.zeros_like(dy__)
    else: 
    '''
     # root fork is comp_r, accumulate derivatives:
    dy__ = dert__[1][1:-1:2, 1:-1:2].copy()  # sparse to align with i__center
    dx__ = dert__[2][1:-1:2, 1:-1:2].copy()
    m__ = dert__[4][1:-1:2, 1:-1:2].copy()

    # compare four diametrically opposed pairs of rim pixels, with Sobel coeffs * rim skip ratio:

    rngSkip = 1
    if rng>2: rngSkip *= (rng-2)*2  # *2 for 9x9, *4 for 17x17

    dy__ += ((i__topleft - i__bottomright) * -1 * rngSkip +
             (i__top - i__bottom) * -2  * rngSkip +
             (i__topright - i__bottomleft) * -1 * rngSkip +
             (i__right - i__left) * 0)

    dx__ += ((i__topleft - i__bottomright) * -1 * rngSkip +
             (i__top - i__bottom) * 0 +
             (i__topright - i__bottomleft) * 1 * rngSkip+
             (i__right - i__left) * 2 * rngSkip)

    g__ = np.hypot(dy__, dx__) - ave  # gradient, recomputed at each comp_r
    '''
    inverse match = SAD, direction-invariant and more precise measure of variation than g
    (all diagonal derivatives can be imported from prior 2x2 comp)
    '''
    m__ += ( abs(i__center - i__topleft) * 1 * rngSkip
           + abs(i__center - i__top) * 2 * rngSkip
           + abs(i__center - i__topright) * 1 * rngSkip
           + abs(i__center - i__right) * 2 * rngSkip
           + abs(i__center - i__bottomright) * 1 * rngSkip
           + abs(i__center - i__bottom) * 2 * rngSkip
           + abs(i__center - i__bottomleft) * 1 * rngSkip
           + abs(i__center - i__left) * 2 * rngSkip
           )

    return (i__center, dy__, dx__, g__, m__), majority_mask__


def comp_a_complex(dert__, ave, prior_forks, mask__=None):  # cross-comp of gradient angle in 2x2 kernels
    '''
    More concise but also more opaque version
    https://github.com/khanh93vn/CogAlg/commit/1f3499c4545742486b89e878240d5c291b81f0ac
    '''
    if mask__ is not None:
        majority_mask__ = (mask__[:-1, :-1].astype(int) +
                           mask__[:-1, 1:].astype(int) +
                           mask__[1:, 1:].astype(int) +
                           mask__[1:, :-1].astype(int)
                           ) > 1
    else:
        majority_mask__ = None

    i__, dy__, dx__, g__, m__ = dert__[:5]  # day__,dax__,ga__,ma__ are recomputed

    az__ = dx__ + 1j * dy__  # take the complex number (z), phase angle is now atan2(dy, dx)

    with np.errstate(divide='ignore', invalid='ignore'):  # suppress numpy RuntimeWarning
        az__ /=  np.absolute(az__)  # normalize by g, cosine = a__.real, sine = a__.imag

    # a__ shifted in 2x2 kernel, rotate 45 degrees counter-clockwise to cancel clockwise rotation in frame_blobs:
    az__left = az__[:-1, :-1]  # was topleft
    az__top = az__[:-1, 1:]  # was topright
    az__right = az__[1:, 1:]  # was botright
    az__bottom = az__[1:, :-1]  # was botleft
    '''
    imags and reals of the result are sines and cosines of difference between angles
    a__ is rotated 45 degrees counter-clockwise:
    '''
    dazx__ = az__right * az__left.conj()  # cos_az__right + j * sin_az__left
    dazy__ = az__bottom * az__top.conj()  # cos_az__bottom * j * sin_az__top

    dax__ = np.angle(dazx__)  # phase angle of the complex number, same as np.atan2(dazx__.imag, dazx__.real)
    day__ = np.angle(dazy__)

    with np.errstate(divide='ignore', invalid='ignore'):  # suppress numpy RuntimeWarning
        ma__ = .125 - (np.abs(dax__) + np.abs(day__)) / 2 * np.pi  # the result is in range in 0-1
    '''
    da deviation from ave da: 0.125 @ 22.5 deg: (π/8 + π/8) / 2*π, or 0.75 @ 45 deg: (π/4 + π/4) / 2*π
    sin(-θ) = -sin(θ), cos(-θ) = cos(θ): 
    sin(da) = -sin(-da), cos(da) = cos(-da) => (sin(-da), cos(-da)) = (-sin(da), cos(da))
    '''
    ga__ = np.hypot(day__, dax__) - 0.2777  # same as old formula, atan2 and angle are equivalent
    '''
    ga deviation from ave = 0.2777 @ 22.5 deg, 0.5554 @ 45 degrees = π/4 radians, sqrt(0.5)*π/4 
    '''
    if (prior_forks[-1] == 'g') or (prior_forks[-1] == 'a'):  # root fork is frame_blobs, recompute orthogonal dy and dx
        i__topleft = i__[:-1, :-1]
        i__topright = i__[:-1, 1:]
        i__botright = i__[1:, 1:]
        i__botleft = i__[1:, :-1]
        dy__ = (i__botleft + i__botright) - (i__topleft + i__topright)  # decomposition of two diagonal differences
        dx__ = (i__topright + i__botright) - (i__topleft + i__botleft)  # decomposition of two diagonal differences
    else:
        dy__ = dy__[:-1, :-1]  # passed on as idy, not rotated
        dx__ = dx__[:-1, :-1]  # passed on as idx, not rotated

    i__ = i__[:-1, :-1]  # for summation in Dert
    g__ = g__[:-1, :-1]  # for summation in Dert
    m__ = m__[:-1, :-1]

    return (i__, dy__, dx__, g__, m__, dazy__, dazx__, ga__, ma__), majority_mask__  # dazx__, dazy__ may not be needed


def angle_diff_complex(az2, az1):  # unpacked in comp_a
    '''
    compare phase angle of az1 to that of az2
    az1 = cos_1 + j*sin_1
    az2 = cos_2 + j*sin_2
    (sin_1, cos_1, sin_2, cos_2 below in angle_diff2)
    Assuming that the formula in angle_diff is correct, the result is:
    daz = cos_da + j*sin_da
    Substitute cos_da, sin_da (from angle_diff below):
    daz = (cos_1*cos_2 + sin_1*sin_2) + j*(cos_1*sin_2 - sin_1*cos_2)
        = (cos_1 - j*sin_1)*(cos_2 + j*sin_2)
    Substitute (1) and (2) into the above eq:
    daz = az1 * complex_conjugate_of_(az2)
    az1 = a + bj; az2 = c + dj
    daz = (a + bj)(c - dj)
        = (ac + bd) + (ad - bc)j
        (same as old formula, in angle_diff2() below)
     '''
    return az2 * az1.conj()  # imags and reals of the result are sines and cosines of difference between angles