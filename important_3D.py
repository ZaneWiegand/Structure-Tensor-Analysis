# %%
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import convolve2d
from skimage.filters import gaussian
from skimage import transform
import tifffile as tf
from tqdm import tqdm
# %%


def change_z_dim(img, z_dim):
    if img.ndim == 3:
        if z_dim == 2:
            new_img = np.zeros([img.shape[0], img.shape[1], img.shape[2]])
            for i in range(img.shape[z_dim]):
                new_img[:, :, i] = img[:, :, i]
            return new_img
        elif z_dim == 1:
            new_img = np.zeros([img.shape[0], img.shape[2], img.shape[1]])
            for i in range(img.shape[z_dim]):
                new_img[:, :, i] = img[:, i, :]
            return new_img
        elif z_dim == 0:
            new_img = np.zeros([img.shape[1], img.shape[2], img.shape[0]])
            for i in range(img.shape[z_dim]):
                new_img[:, :, i] = img[i, :, :]
            return new_img
        else:
            raise ValueError("Input correct z_dim: 0, 1 or 2")
    elif img.ndim == 4:
        if z_dim == 0:
            return img
        elif z_dim == 1:
            new_img = np.zeros([img.shape[1], img.shape[0],
                                img.shape[2], img.shape[3]]).astype(np.uint8)
            for i in range(img.shape[z_dim]):
                new_img[i, :, :, :] = img[:, i, :, :]
            return new_img
        elif z_dim == 2:
            new_img = np.zeros([img.shape[2], img.shape[0],
                               img.shape[1], img.shape[3]]).astype(np.uint8)
            for i in range(img.shape[z_dim]):
                new_img[i, :, :, :] = img[:, :, i, :]
            return new_img
        else:
            raise ValueError(
                "Input image shape: (Z,H,W,C), Input correct z_dim: 0, 1 or 2")


# %%
image_3D = tf.imread('ground-truth.tif').astype(np.uint8)
image_3D = change_z_dim(image_3D, 0)
print(image_3D.shape)
print(image_3D.dtype)
print(image_3D.min())
print(image_3D.max())
print(np.median(image_3D))

i = np.random.randint(0, image_3D.shape[2])
plt.imshow(image_3D[:, :, i], cmap=plt.cm.gray)
# %%
# pre-process


def preprocess_img(img_stack, xy_resolution, z_resolution, downsample_ratio):
    # estimate variance (sigma**2) from FWHM values     [um**2]
    sigma2_xy = xy_resolution ** 2 / (8 * np.log(2))
    sigma2_z = z_resolution ** 2 / (8 * np.log(2))
    # estimate variance (sigma_s**2) of Gaussian kernel [um**2]
    sigma2_s = np.abs(sigma2_z - sigma2_xy)
    # estimate SD of Gaussian Kernel for spatial LP filtering [um]
    sigma_blur = np.sqrt(sigma2_s)

    sample_X = int(img_stack.shape[0]*downsample_ratio)
    sample_Y = int(img_stack.shape[1]*downsample_ratio)
    sample_Z = int(img_stack.shape[2]*downsample_ratio)

    sampled = np.zeros((sample_X, sample_Y, sample_Z), dtype=np.uint8)

    for z in range(img_stack.shape[2]):
        blurred = gaussian(image=img_stack[:, :, z],
                           sigma=sigma_blur, mode='reflect')
        blurred_downsample = transform.resize(
            blurred, output_shape=(sample_X, sample_Y))
        for a in range(int(z*downsample_ratio), int((z+1)*downsample_ratio)):
            sampled[:, :, a] = blurred_downsample
    img_stack = 255 - sampled
    return img_stack


image_3D = preprocess_img(image_3D, 1, 1, 1)

print(image_3D.shape)
print(image_3D.dtype)
print(image_3D.min())
print(image_3D.max())
print(np.median(image_3D))

i = np.random.randint(0, image_3D.shape[2])
plt.imshow(image_3D[:, :, i], cmap=plt.cm.gray)
# %%
# create kernel


def CreateGaussianKernel(sigma, normalizeflag):
    R = np.ceil(2*sigma*np.sqrt(np.log(10)))
    if np.mod(R, 2) == 0:
        R = R+1
    L = np.arange(-R, R+1, 1)
    [X, Y, Z] = np.meshgrid(L, L, L)
    h = (1/(np.sqrt(2*np.pi)*sigma)**3) * \
        np.exp(-(X*X + Y*Y+Z*Z)/(2*sigma*sigma))
    if normalizeflag == 1:
        h = h/np.sum(h)
    return h


def CreateDoGxDoGyDoGzKernel(sigma):
    R = np.ceil(3.57160625*sigma)
    if np.mod(R, 2) == 0:
        R = R+1
    L = np.arange(-R, R+1, 1)
    [X, Y, Z] = np.meshgrid(L, L, L)
    DoGx = -(X/(np.sqrt(2*np.pi)*sigma**2)**3) * \
        np.exp(-(X*X + Y*Y+Z*Z)/(2*sigma**2))
    DoGy = -(Y/(np.sqrt(2*np.pi)*sigma**2)**3) * \
        np.exp(-(X*X + Y*Y+Z*Z)/(2*sigma**2))
    DoGz = -(Z/(np.sqrt(2*np.pi)*sigma**2)**3) * \
        np.exp(-(X*X + Y*Y+Z*Z)/(2*sigma**2))
    return DoGx, DoGy, DoGz


def convolve3d(img, kernel):
    [img_x, img_y, img_z] = np.shape(img)
    [NULL, NULL, f_z] = np.shape(kernel)
    out = np.zeros([img_x, img_y, img_z])
    pad_L = int((f_z-1)/2)
    img_pad = np.zeros([img_x, img_y, img_z+pad_L*2])
    img_pad[:, :, pad_L:pad_L+img_z] = img
    count = 0
    with tqdm(total=img_z) as t:
        for i in range(img_z):
            for j in range(f_z):
                out[:, :, i] = out[:, :, i] + \
                    convolve2d(img_pad[:, :, i+j], kernel[:, :, j], 'same')
            t.update(1)
    return out


# %%
# Standard deviation of derivative-of-gaussian (DoG) kernels [pixel]
sigma_DoG = 4
# Standard deviation of Gaussian kernel [pixel]
sigma_Gauss = 4
GaussianKernel = CreateGaussianKernel(sigma_Gauss, 1)
DoGxKernel, DoGyKernel, DoGzKernel = CreateDoGxDoGyDoGzKernel(sigma_DoG)
# %%
[A, B, C] = np.shape(image_3D)
Tensor_Orientation = np.zeros([A, B, C])
Tensor_AI = np.zeros([A, B, C])
# %%
dImage_dx = convolve3d(image_3D, DoGxKernel)
print('dImage_dx finished!')
dImage_dy = convolve3d(image_3D, DoGyKernel)
print('dImage_dy finished!')
dImage_dz = convolve3d(image_3D, DoGzKernel)
print('dImage_dz finished!')
# %%
Ixx = dImage_dx*dImage_dx
Ixy = dImage_dx*dImage_dy
Ixz = dImage_dx*dImage_dz
Iyy = dImage_dy*dImage_dy
Iyz = dImage_dy*dImage_dz
Izz = dImage_dz*dImage_dz
# %%
Jxx = convolve3d(Ixx, GaussianKernel)
print('Jxx finished!')
Jxy = convolve3d(Ixy, GaussianKernel)
print('Jxy finished!')
Jxz = convolve3d(Ixz, GaussianKernel)
print('Jxz finished!')
Jyy = convolve3d(Iyy, GaussianKernel)
print('Jyy finished!')
Jyz = convolve3d(Iyz, GaussianKernel)
print('Jyz finished!')
Jzz = convolve3d(Izz, GaussianKernel)
print('Jzz finished!')
# %%
dummyEigenvalues11 = np.zeros([A, B, C])
dummyEigenvalues22 = np.zeros([A, B, C])
dummyEigenvalues33 = np.zeros([A, B, C])

with tqdm(total=np.prod([A, B, C])) as t:
    for a in range(A):
        for b in range(B):
            for c in range(C):
                J_a_b_c = np.array([[Jxx[a, b, c], Jxy[a, b, c], Jxz[a, b, c]],
                                    [Jxy[a, b, c], Jyy[a, b, c], Jyz[a, b, c]],
                                    [Jxz[a, b, c], Jyz[a, b, c], Jzz[a, b, c]]])
                Vals, featurevector = np.linalg.eig(J_a_b_c)
                dummyEigenvalues11[a, b, c] = np.real(Vals[0])
                dummyEigenvalues22[a, b, c] = np.real(Vals[1])
                dummyEigenvalues33[a, b, c] = np.real(Vals[2])
                t.update(1)
# %%
# Apply Bigun and Grandlund formula (ref [2]) providing anles in [-pi;pi]
bufferPhi_xy = 0.5*np.angle((Jyy - Jxx) + 1j*2*Jxy)
bufferPhi_yz = 0.5*np.angle((Jyy - Jzz) + 1j*2*Jyz)
bufferPhi_xz = 0.5*np.angle((Jzz - Jxx) + 1j*2*Jxz)
# %%
# Remap negative angles in the positive range, so that angles will be in [0; pi]
bufferPhi_xy[bufferPhi_xy < 0] = np.angle(
    np.exp(1j*bufferPhi_xy[bufferPhi_xy < 0])*np.exp(1j*np.pi))
bufferPhi_yz[bufferPhi_yz < 0] = np.angle(
    np.exp(1j*bufferPhi_yz[bufferPhi_yz < 0])*np.exp(1j*np.pi))
bufferPhi_xz[bufferPhi_xz < 0] = np.angle(
    np.exp(1j*bufferPhi_xz[bufferPhi_xz < 0])*np.exp(1j*np.pi))
# %%
# Save the orientation map in radians
Tensor_Orientation = (bufferPhi_xy+bufferPhi_xz+bufferPhi_yz)/3
# %%
print(Tensor_Orientation.shape)
print(Tensor_Orientation.dtype)
# %%
# Save the anisotropy map
Tensor_AI_1122 = abs(dummyEigenvalues11 - dummyEigenvalues22 + 1e-8) / \
    abs(dummyEigenvalues11 + dummyEigenvalues22 + 1e-8)
Tensor_AI_1133 = abs(dummyEigenvalues11 - dummyEigenvalues33 + 1e-8) / \
    abs(dummyEigenvalues11 + dummyEigenvalues33 + 1e-8)
Tensor_AI_2233 = abs(dummyEigenvalues22 - dummyEigenvalues33 + 1e-8) / \
    abs(dummyEigenvalues22 + dummyEigenvalues33 + 1e-8)
# %%
Tensor_AI = (Tensor_AI_1122+Tensor_AI_1133+Tensor_AI_2233)/3
# %%
HueThetaZero = 0
HueThetaPi = 1
H = HueThetaZero + (1/np.pi)*(HueThetaPi - HueThetaZero)*Tensor_Orientation
S = Tensor_AI
V = 1 - image_3D/255
# %%
image_HSV = np.zeros(
    [image_3D.shape[2], image_3D.shape[0], image_3D.shape[1], 3])
for item in range(image_HSV.shape[0]):
    image_HSV[item, :, :, 0] = H[:, :, item]
    image_HSV[item, :, :, 1] = S[:, :, item]
    image_HSV[item, :, :, 2] = V[:, :, item]
# %%


def HSV2RGB(hsv):
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    h = 6*h
    k = np.floor(h)
    p = h-k
    t = 1-s
    n = 1-s*p
    p = 1-(s*(1-p))
    kc = (k == 0)
    r = kc
    g = kc*p
    b = kc*t
    kc = (k == 1)
    r = r + kc*n
    g = g + kc
    b = b + kc*t
    kc = (k == 2)
    r = r + kc*t
    g = g + kc
    b = b + kc*p
    kc = (k == 3)
    r = r + kc*t
    g = g + kc*n
    b = b + kc
    kc = (k == 4)
    r = r + kc*p
    g = g + kc*t
    b = b + kc
    kc = (k == 5)
    r = r + kc
    g = g + kc*t
    b = b + kc*n
    kc = (k == 6)
    r = r + kc
    g = g + kc*p
    b = b + kc*t
    out = np.dstack((r, g, b))
    out[:, :, 0] = v/np.max(out)*out[:, :, 0]
    out[:, :, 1] = v/np.max(out)*out[:, :, 1]
    out[:, :, 2] = v/np.max(out)*out[:, :, 2]
    return out


# %%
image_RGB = np.zeros(image_HSV.shape)
for i in range(image_HSV.shape[0]):
    image_RGB[i, :, :, :] = HSV2RGB(image_HSV[i, :, :, :])
# %%
image_OUT = (255*image_RGB).astype(np.uint8)
# %%
i = np.random.randint(0, image_OUT.shape[0])
plt.imshow(image_OUT[i, :, :, :])
# %%
image_OUT_0 = change_z_dim(image_OUT, 0)
tf.imwrite('../STA-Results/3D_output_0.tif', image_OUT_0)
image_OUT_1 = change_z_dim(image_OUT, 1)
tf.imwrite('../STA-Results/3D_output_1.tif', image_OUT_1)
image_OUT_2 = change_z_dim(image_OUT, 2)
tf.imwrite('../STA-Results/3D_output_2.tif', image_OUT_2)
