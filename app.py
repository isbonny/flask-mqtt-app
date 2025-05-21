from flask import Flask, request, render_template_string
import pandas as pd
import numpy as np
from scipy.signal import find_peaks, savgol_filter, butter, filtfilt
from scipy.fftpack import fft
import os

app = Flask(__name__)

# 高通濾波函式
def highpass_filter(data, cutoff=0.01, fs=11, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return filtfilt(b, a, data)

# 呼吸分析函式（把你Colab邏輯包起來）
def analyze_breath(df):
    x_acc = df['XAcc'].values
    sampling_rate = 11

    mid_index = len(x_acc) // 2
    x_acc = x_acc[mid_index - 100: mid_index + 100]
    sample_indices = np.arange(len(x_acc))
    time_axis = sample_indices / sampling_rate

    # 信號前處理
    z_score = (x_acc - np.mean(x_acc)) / np.std(x_acc)
    x_acc_clean = x_acc[np.abs(z_score) < 3]

    if len(x_acc_clean) < 10:
        return 0  # 若資料太少，回傳0

    x_acc_detrended = highpass_filter(x_acc_clean, fs=sampling_rate)
    x_acc_normalized = (x_acc_detrended - np.min(x_acc_detrended)) / (np.max(x_acc_detrended) - np.min(x_acc_detrended))

    # 平滑濾波
    x_acc_smooth = savgol_filter(x_acc_normalized, window_length=30, polyorder=3)

    # 頻域分析(FFT)
    N = len(x_acc_smooth)
    xf = np.fft.fftfreq(N, 1 / sampling_rate)
    yf = np.abs(fft(x_acc_smooth))

    valid_indices = (xf > 0.2) & (xf < 0.5)
    if not np.any(valid_indices):
        dominant_freq = 0.2  # 預設值
    else:
        dominant_freq = xf[valid_indices][np.argmax(yf[valid_indices])]

    expected_breath_period = 1 / dominant_freq if dominant_freq > 0 else 5

    # 呼吸峰值偵測
    std_dev = np.std(x_acc_smooth)
    adaptive_threshold = 1.5 * std_dev
    peaks, _ = find_peaks(x_acc_smooth, height=adaptive_threshold, distance=sampling_rate * expected_breath_period)

    if len(peaks) < 2:
        return 0

    breath_intervals_samples = np.diff(peaks)
    breath_intervals = breath_intervals_samples / sampling_rate
    bpm = 60 / np.mean(breath_intervals) if len(breath_intervals) > 1 else 0

    return bpm

# 簡易 HTML 模板
HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>IMU 呼吸偵測分析</title>
</head>
<body>
    <h1>上傳 CSV 檔案進行呼吸頻率分析</h1>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".csv" required>
        <input type="submit" value="上傳並分析">
    </form>
    {% if bpm is not none %}
        <h2>計算結果：</h2>
        {% if bpm > 0 %}
            <p>每分鐘呼吸次數 (BPM)：<strong>{{ bpm | round(2) }}</strong></p>
        {% else %}
            <p>無法判斷有效的呼吸頻率，請確認上傳檔案的資料正確。</p>
        {% endif %}
    {% endif %}
</body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def upload_file():
    bpm = None
    debug_html = ""
    if request.method == "POST":
        if "file" not in request.files:
            bpm = 0
            debug_html = "No file part"
        else:
            file = request.files["file"]
            if file.filename == "":
                bpm = 0
                debug_html = "No selected file"
            else:
                try:
                    df = pd.read_csv(file)
                    debug_html = f"Columns: {df.columns.tolist()}<br>Preview:<br>{df.head().to_html()}"
                    if 'XAcc' not in df.columns:
                        bpm = 0
                        debug_html += "<br>'XAcc' column missing"
                    else:
                        bpm = analyze_breath(df)
                except Exception as e:
                    bpm = 0
                    debug_html = f"Error: {e}"
    return render_template_string(HTML_PAGE + "<hr>" + debug_html, bpm=bpm)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
