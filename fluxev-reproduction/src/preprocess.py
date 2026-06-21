import pandas as pd
import numpy as np

def fill_missing_data(x_raw, missing_mask):
    """论文标准缺失值填充：短缺失线性插值，长缺失周期补偿"""
    x = x_raw.copy()
    n = len(x)
    window_period = 288
    # 第一步：短缺失插值（连续缺失≤5个点）
    for i in range(n):
        if missing_mask[i] == 1:
            left = max(0, i - 5)
            right = min(n - 1, i + 5)
            if np.sum(missing_mask[left:right+1]) <= 5:
                x[i] = np.linspace(x[left], x[right], right - left + 1)[i - left]
    # 第二步：长缺失，取同周期位置均值填充
    for i in range(n):
        if missing_mask[i] == 1 and np.isnan(x[i]):
            pos = i % window_period
            same_pos_vals = []
            j = i - window_period
            while j >= 0:
                if not missing_mask[j]:
                    same_pos_vals.append(x[j])
                j -= window_period
            if len(same_pos_vals) > 0:
                x[i] = np.mean(same_pos_vals)
    return x

def get_micro_train_test(kpi_id="recommendationservice_cpu"):
    data_path = "../fluxev_data/processed/fluxev_total.csv"
    df = pd.read_csv(data_path)
    df_kpi = df[df["KPI ID"] == kpi_id].sort_values("timestamp").reset_index(drop=True)
    x_raw = df_kpi["value"].values
    missing_mask = df_kpi["missing"].values
    label_all = df_kpi["label"].values
    is_test = df_kpi["is_test"].values

    # 论文缺失填充
    x_fill = fill_missing_data(x_raw, missing_mask)

    # 拆分训练/测试集
    train_x = x_fill[is_test == 0]
    test_x = x_fill[is_test == 1]
    test_label = label_all[is_test == 1]

    # 保存到exp_result
    np.save("../exp_result/train_x.npy", train_x)
    np.save("../exp_result/test_x.npy", test_x)
    np.save("../exp_result/test_label.npy", test_label)
    print("预处理完成！文件输出至 ../exp_result/")
    print(f"训练集长度：{len(train_x)}，测试集长度：{len(test_x)}")
    return train_x, test_x, test_label

if __name__ == "__main__":
    get_micro_train_test()