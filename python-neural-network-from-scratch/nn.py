"""
A neural network from scratch: only numpy, no PyTorch or TensorFlow.

Implements: dense layers, ReLU, softmax + cross-entropy, backpropagation,
mini-batch training with the Adam optimizer, L2 regularization, and accuracy tracking.
"""
import numpy as np


class Dense:
    """Fully-connected layer: y = x @ W + b"""

    def __init__(self, n_in, n_out, rng):
        # He initialization keeps signals from exploding or vanishing with ReLU.
        self.W = rng.normal(0, np.sqrt(2 / n_in), (n_in, n_out))
        self.b = np.zeros(n_out)
        # Adam optimizer state (moving averages of gradients and squared gradients)
        self.mW, self.vW = np.zeros_like(self.W), np.zeros_like(self.W)
        self.mb, self.vb = np.zeros_like(self.b), np.zeros_like(self.b)

    def forward(self, x):
        self.x = x
        return x @ self.W + self.b

    def backward(self, grad_out, l2):
        # Chain rule: how much did each weight contribute to the loss?
        self.dW = self.x.T @ grad_out + l2 * self.W
        self.db = grad_out.sum(axis=0)
        return grad_out @ self.W.T  # gradient for the previous layer

    def adam_step(self, lr, t, beta1=0.9, beta2=0.999, eps=1e-8):
        for p, g, m, v in ((self.W, self.dW, self.mW, self.vW), (self.b, self.db, self.mb, self.vb)):
            m[:] = beta1 * m + (1 - beta1) * g
            v[:] = beta2 * v + (1 - beta2) * g * g
            m_hat = m / (1 - beta1 ** t)
            v_hat = v / (1 - beta2 ** t)
            p -= lr * m_hat / (np.sqrt(v_hat) + eps)


class ReLU:
    def forward(self, x):
        self.mask = x > 0
        return x * self.mask

    def backward(self, grad_out, l2=None):
        return grad_out * self.mask


def softmax(logits):
    shifted = logits - logits.max(axis=1, keepdims=True)  # for numerical stability
    e = np.exp(shifted)
    return e / e.sum(axis=1, keepdims=True)


class NeuralNet:
    def __init__(self, sizes, seed=0, l2=1e-4):
        rng = np.random.default_rng(seed)
        self.layers = []
        for i, (a, b) in enumerate(zip(sizes, sizes[1:])):
            self.layers.append(Dense(a, b, rng))
            if i < len(sizes) - 2:
                self.layers.append(ReLU())
        self.l2 = l2
        self.t = 0

    def logits(self, x):
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def predict_proba(self, x):
        return softmax(self.logits(x))

    def predict(self, x):
        return self.logits(x).argmax(axis=1)

    def train_batch(self, x, y, lr):
        probs = softmax(self.logits(x))
        n = len(y)
        loss = -np.log(probs[np.arange(n), y] + 1e-12).mean()
        loss += 0.5 * self.l2 * sum((l.W ** 2).sum() for l in self.layers if isinstance(l, Dense))

        # Gradient of softmax + cross-entropy has a neat closed form: probs - one_hot
        grad = probs.copy()
        grad[np.arange(n), y] -= 1
        grad /= n
        for layer in reversed(self.layers):
            grad = layer.backward(grad, self.l2)

        self.t += 1
        for layer in self.layers:
            if isinstance(layer, Dense):
                layer.adam_step(lr, self.t)
        return loss

    def fit(self, x, y, epochs=300, batch_size=64, lr=0.01, x_val=None, y_val=None, seed=0, log_every=50):
        rng = np.random.default_rng(seed)
        history = {"loss": [], "train_acc": [], "val_acc": []}
        for epoch in range(1, epochs + 1):
            order = rng.permutation(len(x))
            losses = [self.train_batch(x[order[i:i + batch_size]], y[order[i:i + batch_size]], lr)
                      for i in range(0, len(x), batch_size)]
            history["loss"].append(float(np.mean(losses)))
            history["train_acc"].append(self.accuracy(x, y))
            if x_val is not None:
                history["val_acc"].append(self.accuracy(x_val, y_val))
            if log_every and (epoch % log_every == 0 or epoch == 1):
                val = f"  val acc {history['val_acc'][-1]:.1%}" if x_val is not None else ""
                print(f"epoch {epoch:4d}  loss {history['loss'][-1]:.4f}  train acc {history['train_acc'][-1]:.1%}{val}")
        return history

    def accuracy(self, x, y):
        return float((self.predict(x) == y).mean())


def gradient_check(seed=0):
    """Compare backprop gradients against numerical (finite-difference) gradients."""
    rng = np.random.default_rng(seed)
    net = NeuralNet([2, 5, 3], seed=seed, l2=0.0)
    x = rng.normal(size=(4, 2))
    y = rng.integers(0, 3, 4)
    layer = net.layers[0]

    def loss_fn():
        p = net.predict_proba(x)
        return -np.log(p[np.arange(len(y)), y]).mean()

    # analytic gradient
    p = net.predict_proba(x)
    grad = p.copy()
    grad[np.arange(len(y)), y] -= 1
    grad /= len(y)
    for l in reversed(net.layers):
        grad = l.backward(grad, 0.0)
    analytic = layer.dW.copy()

    numeric = np.zeros_like(layer.W)
    h = 1e-5
    for i in np.ndindex(layer.W.shape):
        old = layer.W[i]
        layer.W[i] = old + h
        plus = loss_fn()
        layer.W[i] = old - h
        minus = loss_fn()
        layer.W[i] = old
        numeric[i] = (plus - minus) / (2 * h)
    rel_error = np.abs(analytic - numeric).max() / (np.abs(analytic).max() + np.abs(numeric).max())
    return rel_error
