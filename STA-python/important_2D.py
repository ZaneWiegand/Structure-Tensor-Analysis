# %%
import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import convolve2d
import tifffile as tf
from tqdm import tqdm
# %% transform unit16 image intensity to 0-255


def preprocess_img(img, downsample_times=0, reverse=True):
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.uint8)
    else:
        img = img.astype(np.uint8)
    if downsample_times != 0:
        for i in range(downsample_times):
            img = cv2.pyrDown(img)
    if reverse == True:
        img = 255 - img
    return img


# %% transform unit16 image intensity to 0-255
# img = cv2.imread('./test_img.jpg')
img = tf.imread('./input.tif')
img = preprocess_img(img, 0, True)
# img = norm_img(img, False)

# %%
plt.imshow(img, cmap='gray')
print(img.shape)
print(img.dtype)
print(img.min())
print(img.max())
print(np.median(img))
# %%
# * kernel function creation


def CreateGaussianKernel(sigma, normalizeflag):
    R = np.ceil(2 * sigma * np.sqrt(np.log(10)))  # kernel size
    [X, Y] = np.meshgrid(np.arange(-R, R + 1, 1), np.arange(-R, R + 1, 1))
    h = (1 / (2 * np.pi * sigma * sigma)) * np.exp(
        -(X * X + Y * Y) / (2 * sigma * sigma)
    )
    if normalizeflag == 1:
        h = h / np.sum(h)
    return h


def CreateDoGxDoGyKernel(sigma):
    R = np.ceil(3.57160625 * sigma)  # kernel size
    [X, Y] = np.meshgrid(np.arange(-R, R + 1, 1), np.arange(-R, R + 1, 1))
    DoGx = -(X / (2 * np.pi * sigma ** 4)) * \
        np.exp(-(X * X + Y * Y) / (2 * sigma ** 2))
    DoGy = -(Y / (2 * np.pi * sigma ** 4)) * \
        np.exp(-(X * X + Y * Y) / (2 * sigma ** 2))
    return DoGx, DoGy


# %%
# Perform Structure Tensor (ST) analysis on a gray scale double prec. image
#           1) field Tensor_Orientation will be contain with the primary
#              orientation of the ST. It is a RxC matrix, where each
#              element (r,c) is the orientation at location (r,c), ranging
#              in [0; pi] radians.
#           2) Tensor#AI will be contain the anisotropy index (AI) of the ST.
#              It is a a RxC matrix, where each element (r,c) is a the AI
#              at location (r,c), defined as
#                              (L1 - L2)/(L1 + L2)
#              Being L1>=L2 the two eigenvalues of the ST at location
#              (r,c).
# ALGORITHM
# For each pixel of input image img, the ST is defined as the 2x2 matrix
#      | Jxx  Jxy |
# J =  |          |
#      | Jxy  Jyy |
# with
#      Jxx = w * (Ix Ix)
#      Jxy = w * (Ix Iy)
#      Jyy = w * (Iy Iy)
# Above,
# * is the convolution operator;
# w is an isotropic Gaussian kernel with standard deviation s;
# Ix and Iy are estimates of the partial derivatives of
# img with respect to x and y, obtained convolving img
# with derivative of Gaussian (DoG) kernels.
# For a given J, the anisotropy index is
#   AI = (L1 - L2)/(L1 + L2)
# having defined L1 and L2 as the largest and smallest eigenvalues of J.
# The primary orientation of J in degrees is defined as the orientation of
# the eigenvector associated to L2, in the range [0; pi] degrees.
# REFERENCES
# [1] Matthew D. Budde and Joseph A. Frank, NeuroImage, Volume 63, Issue 1,
# 15 October 2012, Pages 1 - 10:
# "Examining brain microstructure using structure tensor analysis of
#  histological sections".
# [2] Josef Bigun and Gosta H. Granlund, Proceedings of the IEEE, first
# International Conference on Computer Vision, London, June 1987:
# "Optimal orientation detection of linear simmetry".
# %%
# * Standard deviation of derivative-of-gaussian (DoG) kernels [pixel]
sigma_DoG = 4  # !the largerer the structure, the bigger the sigma
# * Standard deviation of Gaussian kernel [pixel]
sigma_Gauss = 4
# !the largerer the structure, the bigger the sigma
GaussianKernel = CreateGaussianKernel(sigma_Gauss, 1)
DoGxKernel, DoGyKernel = CreateDoGxDoGyKernel(sigma_DoG)

plt.figure()
plt.subplot(1, 3, 1)
plt.imshow(GaussianKernel)
plt.subplot(1, 3, 2)
plt.imshow(DoGxKernel)
plt.subplot(1, 3, 3)
plt.imshow(DoGyKernel)
plt.tight_layout()

# %%
[R, C] = np.shape(img)
Tensor_Orientation = np.zeros([R, C])
Tensor_AI = np.zeros([R, C])
# %%
dImage_dx = convolve2d(img, DoGxKernel, "same")
dImage_dy = convolve2d(img, DoGyKernel, "same")

plt.figure()
plt.subplot(1, 2, 1)
plt.imshow(dImage_dx, cmap='gray')
plt.subplot(1, 2, 2)
plt.imshow(dImage_dy, cmap='gray')
plt.tight_layout()

# %%
Ixx = dImage_dx * dImage_dx
Ixy = dImage_dx * dImage_dy
Iyy = dImage_dy * dImage_dy

plt.figure()
plt.subplot(1, 3, 1)
plt.imshow(Ixx, cmap='gray')
plt.subplot(1, 3, 2)
plt.imshow(Ixy, cmap='gray')
plt.subplot(1, 3, 3)
plt.imshow(Iyy, cmap='gray')
plt.tight_layout()

# %%
Jxx = convolve2d(Ixx, GaussianKernel, "same")
print("Jxx finished!")
Jxy = convolve2d(Ixy, GaussianKernel, "same")
print("Jxy finished!")
Jyy = convolve2d(Iyy, GaussianKernel, "same")
print("Jyy finished!")
# %%
dummyEigenvalues11 = np.zeros([R, C])
dummyEigenvalues22 = np.zeros([R, C])
# %%
TOT = R * C
count = 0
with tqdm(total=np.prod([R, C])) as t:
    for rr in range(R):
        for cc in range(C):
            J_rr_cc = np.array([[Jxx[rr, cc], Jxy[rr, cc]],
                               [Jxy[rr, cc], Jyy[rr, cc]]])
            Vals, featurevector = np.linalg.eig(J_rr_cc)
            dummyEigenvalues11[rr, cc] = Vals[0]
            dummyEigenvalues22[rr, cc] = Vals[1]
            t.update(1)
# %%
# Apply Bigun and Grandlund formula (ref [2]) providing anles in [-pi;pi]
bufferPhi = 0.5 * np.angle((Jyy - Jxx) + 1j * 2 * Jxy)
# %%
# Remap negative angles in the positive range, so that angles will be in [0; pi]
bufferPhi[bufferPhi < 0] = np.angle(
    np.exp(1j * bufferPhi[bufferPhi < 0]) * np.exp(1j * np.pi)
)
# %%
# Save the orientation map in radians
Tensor_Orientation = bufferPhi
# %%
# Save the anisotropy map
Tensor_AI = abs(dummyEigenvalues11 - dummyEigenvalues22 + 1e-8) / abs(
    dummyEigenvalues11 + dummyEigenvalues22 + 1e-8
)
# %%
HueThetaZero = 0
HueThetaPi = 1
H = HueThetaZero + (1 / np.pi) * (HueThetaPi -
                                  HueThetaZero) * Tensor_Orientation
S = Tensor_AI
V = 1 - img / 255
# %%
image_HSV = np.dstack((H, S, V))
print(image_HSV.shape)
print(image_HSV.dtype)
# %%


def HSV2RGB(hsv):
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    h = 6 * h
    k = np.floor(h)
    p = h - k
    t = 1 - s
    n = 1 - s * p
    p = 1 - (s * (1 - p))
    kc = k == 0
    r = kc
    g = kc * p
    b = kc * t
    kc = k == 1
    r = r + kc * n
    g = g + kc
    b = b + kc * t
    kc = k == 2
    r = r + kc * t
    g = g + kc
    b = b + kc * p
    kc = k == 3
    r = r + kc * t
    g = g + kc * n
    b = b + kc
    kc = k == 4
    r = r + kc * p
    g = g + kc * t
    b = b + kc
    kc = k == 5
    r = r + kc
    g = g + kc * t
    b = b + kc * n
    kc = k == 6
    r = r + kc
    g = g + kc * p
    b = b + kc * t
    out = np.dstack((r, g, b))
    out[:, :, 0] = v / np.max(out) * out[:, :, 0]
    out[:, :, 1] = v / np.max(out) * out[:, :, 1]
    out[:, :, 2] = v / np.max(out) * out[:, :, 2]
    return out


# %%
image_RGB = HSV2RGB(image_HSV)
# %%
image_OUT = (255 * image_RGB).astype(np.uint8)
# %%
plt.imshow(image_OUT)
# %%
plt.imsave("./STA_out.jpg", image_OUT)
