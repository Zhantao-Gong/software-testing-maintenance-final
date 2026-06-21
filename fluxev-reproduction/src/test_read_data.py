import pandas as pd
import matplotlib.pyplot as plt
# 消除中文绘图字体缺失警告
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

def print_all_kpi():
    data_path = "../fluxev_data/processed/fluxev_total.csv"
    df = pd.read_csv(data_path)
    print("===== 文件内全部KPI ID清单（共4000+条数据） =====")
    all_kpi = df["KPI ID"].unique()
    for kpi in all_kpi:
        print(kpi)
    cpu_kpi_list = [k for k in all_kpi if "cpu" in k.lower()]
    print("\n===== 所有CPU相关指标（用于正式实验） =====")
    print(cpu_kpi_list)
    return all_kpi

def load_micro_data(kpi_id):
    data_path = "../fluxev_data/processed/fluxev_total.csv"
    df = pd.read_csv(data_path)
    df_kpi = df[df["KPI ID"] == kpi_id].sort_values("timestamp").reset_index(drop=True)
    print(f"\n选中指标：{kpi_id}")
    print(f"该指标总数据条数：{len(df_kpi)}")
    print("字段列表：", df_kpi.columns.tolist())
    print("训练/测试样本数量：")
    print(df_kpi["is_test"].value_counts())
    print("故障类型分布：")
    print(df_kpi["fault_type"].value_counts())
    # 输出时序预览图
    plt.figure(figsize=(14,4))
    plt.plot(df_kpi["timestamp"], df_kpi["value"])
    plt.title(f"{kpi_id} 原始时序预览")
    plt.savefig("../exp_result/data_preview.png")
    plt.close()
    return df_kpi

if __name__ == "__main__":
    # 第一步：打印全部KPI清单（已完成，可注释）
    # print_all_kpi()
    # 第二步：选用推荐CPU指标运行校验
    df = load_micro_data("recommendationservice_cpu")