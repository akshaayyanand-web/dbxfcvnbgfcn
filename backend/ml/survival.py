"""Survival analysis for right-censored flame lifetimes.

* ``kaplan_meier``     -- non-parametric survival curve (descriptive baseline).
* ``concordance_index`` -- Harrell's C for censored data (ranking accuracy; 0.5 = no skill).
* ``AFTModel``          -- parametric accelerated-failure-time regression
                          ``log T = x . beta + sigma * eps``, fitted by maximum likelihood
                          with censoring; ``eps`` is standard minimum-Gumbel (Weibull AFT)
                          or standard normal (log-normal AFT).

Why AFT: ``exp(beta_j)`` is a *time ratio*: the multiplicative change in
lifetime per unit of feature ``j``, holding the others fixed. With
observed-information standard errors, this gives an inherently interpretable
model with confidence intervals, which suits ~150 experiments better than a
black-box model.

Censoring assumption: censoring is independent of the lifetime given the
features. In s-Flame some tests were stopped by a burner temperature limit,
which may relate to flame proximity to the burner. This is a stated limitation
(SCIENTIFIC_ASSUMPTIONS.md, A-ML-3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats


# --------------------------------------------------------------------- descriptive


def kaplan_meier(t: np.ndarray, event: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(times, survival)`` at each distinct event time (step function, right-continuous)."""
    t = np.asarray(t, float)
    e = np.asarray(event, bool)
    if t.size == 0:
        return np.array([]), np.array([])
    times = np.unique(t[e])
    s, surv = 1.0, []
    for tt in times:
        at_risk = np.sum(t >= tt)
        d = np.sum((t == tt) & e)
        s *= 1.0 - d / at_risk
        surv.append(s)
    return times, np.array(surv)


def km_median(t: np.ndarray, event: np.ndarray) -> float:
    """Kaplan-Meier median (``nan`` if the curve never drops to 0.5)."""
    times, surv = kaplan_meier(t, event)
    below = np.flatnonzero(surv <= 0.5)
    return float(times[below[0]]) if below.size else math.nan


def concordance_index(t: np.ndarray, event: np.ndarray, predicted_time: np.ndarray) -> float:
    """Harrell's C: among comparable pairs (the shorter time is an observed event), the fraction where the
    shorter observed time also has the shorter predicted time. Ties in prediction count 0.5."""
    t = np.asarray(t, float)
    e = np.asarray(event, bool)
    p = np.asarray(predicted_time, float)
    num = den = 0.0
    for i in np.flatnonzero(e):
        later = t > t[i]
        den += later.sum()
        num += np.sum(p[later] > p[i]) + 0.5 * np.sum(p[later] == p[i])
    return float(num / den) if den else math.nan


# ----------------------------------------------------------------------------- AFT

DISTRIBUTIONS = ("weibull", "lognormal")


def _logpdf_logsf(z: np.ndarray, dist: str) -> tuple[np.ndarray, np.ndarray]:
    if dist == "weibull":
        ez = np.exp(np.clip(z, -50, 50))
        return z - ez, -ez
    return stats.norm.logpdf(z), stats.norm.logsf(z)


def _eps_quantile(q: np.ndarray | float, dist: str) -> np.ndarray | float:
    if dist == "weibull":
        return np.log(-np.log1p(-np.asarray(q, float)))
    return stats.norm.ppf(q)


@dataclass
class AFTModel:
    distribution: str = "weibull"
    l2: float = 0.0                       # optional ridge penalty on non-intercept coefficients
    coef_: np.ndarray | None = None       # [intercept, beta_1..beta_p]
    log_sigma_: float | None = None
    cov_: np.ndarray | None = None        # covariance of [coef, log_sigma]
    loglik_: float | None = None
    n_: int = 0
    n_events_: int = 0
    converged_: bool = False
    notes: list[str] = field(default_factory=list)

    def _nll(self, theta: np.ndarray, X: np.ndarray, logt: np.ndarray, e: np.ndarray) -> float:
        beta, log_sigma = theta[:-1], theta[-1]
        sigma = math.exp(log_sigma)
        z = (logt - X @ beta) / sigma
        lpdf, lsf = _logpdf_logsf(z, self.distribution)
        ll = np.sum(e * (lpdf - log_sigma - logt) + (~e) * lsf)
        return -ll + 0.5 * self.l2 * float(np.sum(beta[1:] ** 2))

    def _grad(self, theta: np.ndarray, X: np.ndarray, logt: np.ndarray, e: np.ndarray) -> np.ndarray:
        """Analytic gradient of the negative log-likelihood."""
        beta, log_sigma = theta[:-1], theta[-1]
        sigma = math.exp(log_sigma)
        z = (logt - X @ beta) / sigma
        if self.distribution == "weibull":
            ez = np.exp(np.clip(z, -50, 50))
            dlpdf, dlsf = 1.0 - ez, -ez
        else:
            lpdf, lsf = _logpdf_logsf(z, self.distribution)
            dlpdf, dlsf = -z, -np.exp(lpdf - lsf)
        dz = np.where(e, dlpdf, dlsf)               # d loglik_i / d z_i
        g_beta = -(X.T @ dz) / sigma                 # dz/dbeta = -x / sigma
        g_ls = float(np.sum(dz * -z) - np.sum(e))    # dz/dlog_sigma = -z ; event term -log_sigma
        grad_ll = np.r_[g_beta, g_ls]
        pen = np.r_[0.0, self.l2 * beta[1:], 0.0]
        return -grad_ll + pen

    def fit(self, X: np.ndarray, t: np.ndarray, event: np.ndarray) -> "AFTModel":
        if self.distribution not in DISTRIBUTIONS:
            raise ValueError(f"distribution must be one of {DISTRIBUTIONS}")
        X = np.asarray(X, float)
        t = np.asarray(t, float)
        e = np.asarray(event, bool)
        if np.any(t <= 0) or not np.all(np.isfinite(t)):
            raise ValueError("Survival times must be positive and finite.")
        if e.sum() < 2:
            raise ValueError("At least two observed events are required.")
        Xd = np.c_[np.ones(len(t)), X]
        logt = np.log(t)
        theta0 = np.r_[np.mean(logt), np.zeros(X.shape[1]), math.log(max(np.std(logt), 0.1))]
        res = optimize.minimize(self._nll, theta0, args=(Xd, logt, e), jac=self._grad, method="BFGS",
                                options={"gtol": 1e-6, "maxiter": 5000})
        theta = res.x
        grad_max = float(np.max(np.abs(self._grad(theta, Xd, logt, e))))
        # Convergence is judged on the gradient at the solution: BFGS may stop with "precision loss"
        # at an optimum (e.g. log-normal tails), which is not a failure when the gradient is ~0.
        self.converged_ = bool(res.success or grad_max < 1e-4)
        self.grad_max_ = grad_max
        if not res.success:
            self.notes.append(f"optimizer: {res.message} (max |gradient| = {grad_max:.1e})")
        self.coef_, self.log_sigma_ = theta[:-1], float(theta[-1])
        self.loglik_ = -float(self._nll(theta, Xd, logt, e)) + 0.5 * self.l2 * float(np.sum(theta[1:-1] ** 2))
        self.n_, self.n_events_ = int(len(t)), int(e.sum())
        H = _numerical_hessian(lambda th: self._nll(th, Xd, logt, e), theta)
        try:
            self.cov_ = np.linalg.inv(H)
            if np.any(np.diag(self.cov_) < 0):
                raise np.linalg.LinAlgError
        except np.linalg.LinAlgError:
            self.cov_ = np.full((len(theta), len(theta)), np.nan)
            self.notes.append("observed information matrix not invertible; no standard errors")
        return self

    @property
    def sigma_(self) -> float:
        return math.exp(self.log_sigma_)

    def linear_predictor(self, X: np.ndarray) -> np.ndarray:
        return np.c_[np.ones(len(X)), np.asarray(X, float)] @ self.coef_

    def predict_quantiles(self, X: np.ndarray, qs=(0.1, 0.5, 0.9)) -> np.ndarray:
        """Lifetime quantiles at the MLE (no parameter uncertainty). Shape ``(n, len(qs))``."""
        mu = self.linear_predictor(X)[:, None]
        return np.exp(mu + self.sigma_ * np.asarray(_eps_quantile(np.asarray(qs), self.distribution))[None, :])

    def predictive_quantiles(self, X: np.ndarray, qs=(0.1, 0.5, 0.9), draws: int = 2000, seed: int = 0) -> np.ndarray:
        """Quantiles of the predictive distribution integrating parameter uncertainty.

        Parameters are drawn from the asymptotic normal ``N(theta_hat, cov)``; for each
        draw one lifetime is sampled, and quantiles are taken over draws.
        """
        if self.cov_ is None or not np.all(np.isfinite(self.cov_)):
            return self.predict_quantiles(X, qs)
        rng = np.random.default_rng(seed)
        theta_hat = np.r_[self.coef_, self.log_sigma_]
        thetas = rng.multivariate_normal(theta_hat, self.cov_, size=draws, method="svd")
        Xd = np.c_[np.ones(len(X)), np.asarray(X, float)]
        mu = Xd @ thetas[:, :-1].T                      # (n, draws)
        sig = np.exp(thetas[:, -1])[None, :]
        u = rng.uniform(1e-9, 1 - 1e-9, size=mu.shape)
        samples = np.exp(mu + sig * _eps_quantile(u, self.distribution))
        return np.quantile(samples, qs, axis=1).T

    def survival(self, X: np.ndarray, t: float) -> np.ndarray:
        z = (math.log(t) - self.linear_predictor(X)) / self.sigma_
        return np.exp(_logpdf_logsf(z, self.distribution)[1])

    def summary(self, names: list[str]) -> list[dict]:
        """Coefficient table with time ratios and Wald 95 % confidence intervals."""
        se = np.sqrt(np.diag(self.cov_))[:-1] if self.cov_ is not None else np.full(len(self.coef_), np.nan)
        rows = []
        for name, b, s in zip(["intercept"] + list(names), self.coef_, se):
            rows.append({
                "term": name, "coef": float(b), "se": float(s),
                "time_ratio": float(math.exp(b)),
                "time_ratio_ci95": [float(math.exp(b - 1.96 * s)), float(math.exp(b + 1.96 * s))]
                if math.isfinite(s) else [math.nan, math.nan],
                "p_value": float(2 * stats.norm.sf(abs(b / s))) if math.isfinite(s) and s > 0 else math.nan,
            })
        return rows

    def aic(self) -> float:
        k = len(self.coef_) + 1
        return 2 * k - 2 * self.loglik_


def _numerical_hessian(f, x: np.ndarray, h: float = 1e-4) -> np.ndarray:
    n = len(x)
    H = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            ei = np.zeros(n)
            ej = np.zeros(n)
            ei[i] = h
            ej[j] = h
            v = (f(x + ei + ej) - f(x + ei - ej) - f(x - ei + ej) + f(x - ei - ej)) / (4 * h * h)
            H[i, j] = H[j, i] = v
    return H


def simulate_aft(X: np.ndarray, beta: np.ndarray, sigma: float, censor_time: float, dist: str = "weibull",
                 seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Simulate censored AFT data (for validation tests): returns ``(observed_time, event)``."""
    rng = np.random.default_rng(seed)
    mu = np.c_[np.ones(len(X)), X] @ beta
    eps = _eps_quantile(rng.uniform(1e-9, 1 - 1e-9, len(X)), dist)
    t_true = np.exp(mu + sigma * eps)
    return np.minimum(t_true, censor_time), t_true <= censor_time


__all__ = ["AFTModel", "concordance_index", "kaplan_meier", "km_median", "simulate_aft"]
