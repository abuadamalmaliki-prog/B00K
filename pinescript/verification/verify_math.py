"""Verify the math that will be ported to Pine.

1. Scalar one-sided HP Kalman (planned Pine port) == matrix version (port of
   alexandrumonahov/hpfilter R/hp1.R, i.e. Meyer-Gohde 2010) exactly.
2. That filter == endpoint of the exact two-sided HP filter on expanding
   samples (the definition of the one-sided / real-time HP filter the BIS uses).
3. Avellaneda-Stoikov average spread reproduces Tables 1-3 of the paper.
4. Cutoff period <-> lambda mapping.
"""
import math
import numpy as np
from scipy.sparse import diags, identity
from scipy.sparse.linalg import spsolve


def hp1_matrix(y, lam):
    """Direct port of R hp1() for one series."""
    q = 1.0 / lam
    F = np.array([[2.0, -1.0], [1.0, 0.0]])
    H = np.array([[1.0, 0.0]])
    Q = np.array([[q, 0.0], [0.0, 0.0]])
    R = 1.0
    x = np.array([[2 * y[0] - y[1]], [3 * y[0] - 2 * y[1]]])
    P = np.array([[1e5, 0.0], [0.0, 1e5]])
    out = np.empty(len(y))
    for j in range(len(y)):
        S = (H @ P @ H.T).item() + R
        K = (F @ P @ H.T) / S
        x = F @ x + K * (y[j] - (H @ x).item())
        Temp = F - K @ H
        P = Temp @ P @ Temp.T + Q + K @ K.T * R
        out[j] = x[1, 0]
    return out


def hp1_scalar(y, lam, x1=None, x2=None):
    """Scalar form planned for Pine (R = 1, symmetric P)."""
    q = 1.0 / lam
    x1 = 2 * y[0] - y[1] if x1 is None else x1
    x2 = 3 * y[0] - 2 * y[1] if x2 is None else x2
    p11, p12, p22 = 1e5, 0.0, 1e5
    out = np.empty(len(y))
    for j in range(len(y)):
        s = p11 + 1.0
        k1 = (2.0 * p11 - p12) / s
        k2 = p11 / s
        v = y[j] - x1
        n1 = 2.0 * x1 - x2 + k1 * v
        n2 = x1 + k2 * v
        a = 2.0 - k1
        b = 1.0 - k2
        np11 = a * a * p11 - 2.0 * a * p12 + p22 + q + k1 * k1
        np12 = b * (a * p11 - p12) + k1 * k2
        np22 = b * b * p11 + k2 * k2
        x1, x2, p11, p12, p22 = n1, n2, np11, np12, np22
        out[j] = x2
    return out


def hp2_endpoint(y, lam):
    n = len(y)
    D = diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(n - 2, n))
    A = (identity(n) + lam * (D.T @ D)).tocsc()
    return spsolve(A, y)[-1]


def lam_from_period(p):
    return 1.0 / (4.0 * (1.0 - math.cos(2.0 * math.pi / p)) ** 2)


rng = np.random.default_rng(7)
y = np.log(100.0) + np.cumsum(rng.normal(0.0003, 0.012, 1500))

y = np.log(100.0) + np.cumsum(rng.normal(0.0003, 0.012, 3000))
for lam in (1600.0, 400000.0, lam_from_period(2000.0)):
    m = hp1_matrix(y, lam)
    s = hp1_scalar(y, lam)
    print(f"lambda={lam:>12.4g}  max|matrix-scalar| = {np.max(np.abs(m - s)):.3e}")
    errs = []
    for t in (50, 200, 600, 1000, 1499, 2999):
        errs.append(abs(s[t] - hp2_endpoint(y[: t + 1], lam)))
    print(f"                  max|kalman - HP endpoint| at t in (50..2999) = {max(errs):.3e}"
          f"  (y scale ~{np.std(np.diff(y)):.3f}/bar)")

print("\nAvellaneda-Stoikov average spread (sigma=2, T=1, k=1.5):")
for g, paper in ((0.1, 1.49), (0.01, 1.35), (1.0, 3.02)):
    avg = g * 4.0 / 2.0 + (2.0 / g) * math.log(1.0 + g / 1.5)
    print(f"  gamma={g:<5} formula={avg:.4f}  paper table={paper}")

print("\nlambda <-> cutoff period:")
for lam in (1600.0, 400000.0):
    p = 2 * math.pi / math.acos(1 - 1 / (2 * math.sqrt(lam)))
    print(f"  lambda={lam:.0f} -> half-gain period {p:.1f} bars; back: {lam_from_period(p):.1f}")

g_t, k_t = 0.1 * 2 * math.sqrt(0.005), 1.5 * 2 * math.sqrt(0.005)
print(f"\nDimensionless A-S params: gamma~={g_t:.5f}, k~={k_t:.5f}")
for H in (10, 50, 100, 200, 600, 700):
    d = (1 / g_t) * math.log(1 + g_t / k_t) - g_t * H / 2
    print(f"  H={H:<4} TP distance = {d:.3f} sigma")
