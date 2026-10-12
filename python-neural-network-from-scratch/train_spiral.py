"""
Train the from-scratch network on a 5-arm spiral, a classic dataset that a straight line
(or logistic regression) cannot separate, then save a decision-boundary picture.

Run:  python train_spiral.py
"""
import matplotlib
matplotlib.use("Agg")  # save to file without opening a window
import matplotlib.pyplot as plt
import numpy as np

from nn import NeuralNet, gradient_check


def make_spiral(points_per_class=300, classes=5, noise=0.3, seed=0):
    rng = np.random.default_rng(seed)
    x, y = [], []
    for c in range(classes):
        r = np.linspace(0.05, 1, points_per_class)
        theta = np.linspace(c * 2 * np.pi / classes, c * 2 * np.pi / classes + 5.5, points_per_class)
        theta += rng.normal(0, noise, points_per_class)
        x.append(np.c_[r * np.sin(theta), r * np.cos(theta)])
        y.append(np.full(points_per_class, c))
    return np.vstack(x), np.concatenate(y)


def main():
    err = gradient_check()
    print(f"Gradient check relative error: {err:.2e}  ({'PASS' if err < 1e-6 else 'FAIL'})\n")

    x, y = make_spiral()
    rng = np.random.default_rng(1)
    order = rng.permutation(len(x))
    split = int(0.8 * len(x))
    train, val = order[:split], order[split:]

    net = NeuralNet([2, 96, 96, 5], seed=0, l2=1e-4)
    history = net.fit(x[train], y[train], epochs=400, batch_size=32, lr=0.005,
                      x_val=x[val], y_val=y[val], log_every=50)
    print(f"\nFinal validation accuracy: {history['val_acc'][-1]:.1%}")

    # ----- figure: decision boundary + training curves
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6), facecolor="#0d0c1d")
    colors = np.array(["#5ef2ff", "#ff4fd8", "#ffd23c", "#7dff7a", "#a98bff"])

    xx, yy = np.meshgrid(np.linspace(-1.2, 1.2, 400), np.linspace(-1.2, 1.2, 400))
    grid_pred = net.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
    from matplotlib.colors import ListedColormap
    ax1.contourf(xx, yy, grid_pred, levels=np.arange(-0.5, 5.5),
                 cmap=ListedColormap(["#123a46", "#46123e", "#46400f", "#1c461b", "#2c2350"]))
    ax1.scatter(x[:, 0], x[:, 1], c=colors[y], s=9, edgecolors="none")
    ax1.set_title("What the network learned", color="white", fontsize=13)

    ax2.plot(history["loss"], color="#ff4fd8", label="training loss")
    ax2b = ax2.twinx()
    ax2b.plot(history["train_acc"], color="#5ef2ff", label="train accuracy")
    ax2b.plot(history["val_acc"], color="#ffd23c", label="validation accuracy")
    ax2b.set_ylim(0, 1.02)
    ax2.set_title("Training progress", color="white", fontsize=13)
    ax2.set_xlabel("epoch", color="white")
    lines = ax2.get_lines() + ax2b.get_lines()
    ax2.legend(lines, [l.get_label() for l in lines], loc="center right", facecolor="#1a1830", labelcolor="white")

    for ax in (ax1, ax2, ax2b):
        ax.set_facecolor("#0d0c1d")
        ax.tick_params(colors="#9a98c0")
        for spine in ax.spines.values():
            spine.set_color("#33305a")
    fig.tight_layout()
    fig.savefig("spiral_result.png", dpi=110, facecolor=fig.get_facecolor())
    print("Saved spiral_result.png")


if __name__ == "__main__":
    main()
