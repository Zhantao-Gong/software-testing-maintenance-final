import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import precision_score, recall_score, f1_score

# 全局参数（与主实验保持一致）
WINDOW_S = 20
PERIOD_L = 60
D = 2
P = 5
ALPHA = 0.3

# EWMA 预测
def ewma_predict(seq, s, alpha=0.3):
    weights = np.array([(1-alpha)**i for i in range(s)])
    weights = weights / weights.sum()
    pred = np.convolve(seq, weights, mode="valid")
    return pred

# 波动提取
def extract_fluctuation(x, s, alpha=0.3):
    fluct = []
    for i in range(s, len(x)):
        window = x[i-s:i]
        pred = ewma_predict(window, s, alpha)[-1]
        e = x[i] - pred
        fluct.append(e)
    return np.array(fluct)

# 一阶平滑
def smooth_first_step(fluct_seq, s):
    f = []
    for i in range(s, len(fluct_seq)):
        win_old = fluct_seq[i-s:i-1]
        win_new = fluct_seq[i-s:i]
        std_old = np.std(win_old)
        std_new = np.std(win_new)
        delta_std = std_new - std_old
        f_i = max(delta_std, 0)
        f.append(f_i)
    return np.array(f)

# 二阶周期平滑
def smooth_second_step(f_seq, l, p, d):
    smoothed = []
    for i in range(2*d, len(f_seq)):
        pos = i % l
        max_ref = 0.0
        for cycle in range(1, p+1):
            ref_idx = i - cycle*l
            if ref_idx < 0:
                continue
            left = max(0, ref_idx - d)
            right = ref_idx + d
            max_val = np.max(f_seq[left:right+1])
            if max_val > max_ref:
                max_ref = max_val
        delta_f = f_seq[i] - max_ref
        s_i = max(delta_f, 0)
        smoothed.append(s_i)
    return np.array(smoothed)

# POT+MOM 阈值计算
def pot_mom_threshold(fluct_seq, q):
    init_t = np.quantile(fluct_seq, q)
    exceed = fluct_seq[fluct_seq > init_t] - init_t
    if len(exceed) < 10:
        return init_t
    mu = np.mean(exceed)
    var = np.var(exceed)
    gamma = 0.5 * (1 - mu**2 / var)
    sigma = 0.5 * mu * (1 + mu**2 / var)
    n = len(fluct_seq)
    nt = len(exceed)
    th = init_t + (sigma / gamma) * ((q * n / nt) ** (-gamma) - 1)
    return th

# 带消融开关的检测函数（已修复长度问题）
def fluxev_detect(train_x, test_x, s, l, d, p, alpha, q, use_second_smooth=True):
    train_fluct = extract_fluctuation(train_x, s)
    train_f = smooth_first_step(train_fluct, s)

    if use_second_smooth:
        train_smooth = smooth_second_step(train_f, l, p, d)
    else:
        train_smooth = train_f

    th = pot_mom_threshold(train_smooth, q)

    test_fluct = extract_fluctuation(test_x, s)
    test_f = smooth_first_step(test_fluct, s)

    if use_second_smooth:
        test_smooth = smooth_second_step(test_f, l, p, d)
    else:
        test_smooth = test_f

    pred_label = (test_smooth > th).astype(int)
    score_seq = test_smooth

    # 前端补0，对齐标签长度
    total_len = len(test_x)
    curr_len = len(pred_label)
    if curr_len < total_len:
        pad_num = total_len - curr_len
        pred_label = np.pad(pred_label, (pad_num, 0), mode="constant", constant_values=0)
        score_seq = np.pad(score_seq, (pad_num, 0), mode="constant", constant_values=0)

    return pred_label, score_seq

# 指标评估
def evaluate(y_true, y_pred):
    p = precision_score(y_true, y_pred, zero_division=0)
    r = recall_score(y_true, y_pred, zero_division=0)
    f = f1_score(y_true, y_pred, zero_division=0)
    return p, r, f

# 绘图
def plot_result(test_raw, score_seq, true_label, pred_label, save_path):
    plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8))
    x_axis = np.arange(len(test_raw))
    ax1.plot(x_axis, test_raw, color="#2E86AB", label="CPU使用率")
    true_fault_idx = np.where(true_label == 1)[0]
    ax1.scatter(true_fault_idx, test_raw[true_fault_idx], c="#E63946", s=20, label="真实故障")
    ax1.set_title("recommendationservice_cpu 测试集原始时序", fontsize=13)
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(x_axis, score_seq, color="#457B9D", label="平滑异常分数")
    pred_fault_idx = np.where(pred_label == 1)[0]
    ax2.scatter(pred_fault_idx, score_seq[pred_fault_idx], c="#2A9D8F", s=20, label="算法预测异常")
    ax2.set_title("FluxEV 异常分数与预测结果", fontsize=13)
    ax2.legend()
    ax2.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()

if __name__ == "__main__":
    train_x = np.load("../exp_result/train_x.npy")
    test_x = np.load("../exp_result/test_x.npy")
    test_label = np.load("../exp_result/test_label.npy")

    target_q = 0.995
    print("===== 【独立文件】二阶周期平滑 消融对照实验 (q = 0.995) =====")

    # 实验组：启用二阶平滑
    print("\n【实验组：启用二阶周期平滑（完整FluxEV）】")
    pred1, score1 = fluxev_detect(train_x, test_x, WINDOW_S, PERIOD_L, D, P, ALPHA, target_q, use_second_smooth=True)
    prec1, rec1, f1_1 = evaluate(test_label, pred1)
    print(f"精确率: {prec1:.4f}")
    print(f"召回率: {rec1:.4f}")
    print(f"F1 分数: {f1_1:.4f}")
    plot_result(test_x, score1, test_label, pred1, "../exp_result/ablation_with_second_smooth.png")

    # 对照组：关闭二阶平滑
    print("\n【对照组：关闭二阶周期平滑】")
    pred2, score2 = fluxev_detect(train_x, test_x, WINDOW_S, PERIOD_L, D, P, ALPHA, target_q, use_second_smooth=False)
    prec2, rec2, f1_2 = evaluate(test_label, pred2)
    print(f"精确率: {prec2:.4f}")
    print(f"召回率: {rec2:.4f}")
    print(f"F1 分数: {f1_2:.4f}")
    plot_result(test_x, score2, test_label, pred2, "../exp_result/ablation_without_second_smooth.png")

    print("\n===== 消融实验执行完毕，图片已保存至 exp_result =====")