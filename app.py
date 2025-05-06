import csv
import json
from flask import Flask, jsonify
from flask import render_template_string, send_file
import paho.mqtt.client as mqtt
import os
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter
from datetime import datetime

# 初始化 Flask 應用
app = Flask(__name__)

# MQTT 設定
MQTT_BROKER = 'broker.emqx.io'  # 使用公共 MQTT Broker
MQTT_PORT = 1883                   # 默認端口
MQTT_SUB_TOPIC = '/imu_data'     # App 發送數據的主題
MQTT_PUB_TOPIC =  '/result'      # 發佈計算後的 BPM 主題

# 儲存接收到的資料
sensor_data_list = []

# 設定 CSV 檔案
csv_filename = 'sensor_data.csv'

# 設置 CSV 文件標題（如果文件不存在則創建）
def initialize_csv():
    if not os.path.isfile(csv_filename):
        with open(csv_filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "UserID", "X", "Y", "Z"])

# MQTT 連線成功後訂閱主題
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_SUB_TOPIC)

# 保存數據到 CSV
def save_to_csv(timestamp, user_id, x, y, z):
    with open(csv_filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, user_id, x, y, z])

# MQTT 訊息處理回調（處理接收到的數據並計算 BPM）
def on_message(client, userdata, msg):
    global sensor_data_list
    try:
        payload = msg.payload.decode('utf-8')
        print(f"Received message: {payload}")

        # 嘗試解析 JSON 格式
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON format, unable to parse the payload: {payload}")
            return

        # 檢查資料是否包含 x, y, z
        if isinstance(data, dict) and 'x' in data and 'y' in data and 'z' in data and 'timestamp' in data and 'userID' in data:
            sensor_data_list.append(data)
            print(f"Processed data: {data}")

            # 保存數據到 CSV
            save_to_csv(data['timestamp'], data['userID'], data['x'], data['y'], data['z'])

        # 防止除以零錯誤：檢查是否有資料
        if len(sensor_data_list) == 0:
            print("Warning: No data to process.")
            return

        # 計算每分鐘的呼吸次數 (BPM)
        bpm = calculate_bpm(sensor_data_list)

        # 發佈計算結果到 MQTT
        client.publish(MQTT_PUB_TOPIC, str(bpm))
        print(f"Published BPM: {bpm}")

    except Exception as e:
        print(f"Error processing message: {e}")

# 計算 BPM 的函數
def calculate_bpm(sensor_data):
    # 提取 X 軸加速度資料
    x_acc = np.array([data['x'] for data in sensor_data])

    # **1. 信號前處理**
    # (1) 高通濾波
    def highpass_filter(data, cutoff=0.01, fs=11, order=2):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='high', analog=False)
        return filtfilt(b, a, data)

    x_acc_detrended = highpass_filter(x_acc, fs=11)

    # (2) 平滑濾波 (Savitzky-Golay)
    x_acc_smooth = savgol_filter(x_acc_detrended, window_length=30, polyorder=3)

    # **2. 偵測呼吸峰值 (吸氣最高點)**
    std_dev = np.std(x_acc_smooth)
    adaptive_threshold = 1.5 * std_dev
    peaks, _ = find_peaks(x_acc_smooth, height=adaptive_threshold)

    # **3. 計算呼吸間隔 (Peak-to-Peak)**
    breath_intervals_samples = np.diff(peaks)  # 峰值間的樣本數
    breath_intervals = breath_intervals_samples / 11  # 換算成秒
    bpm = 60 / np.mean(breath_intervals) if len(breath_intervals) > 1 else 0

    return round(bpm, 2)

# MQTT 客戶端設置
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# 啟動 MQTT 並連接到 broker
def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

# Flask 頁面（可選）
@app.route('/')
def home():
    return 'Flask MQTT BPM Server is Running!'
@app.route('/download')
def download_csv():
    try:
        # 計算最新的 bpm（假設您之前已經有 sensor_data_list）
        if sensor_data_list:
            bpm = calculate_bpm(sensor_data_list)
        else:
            bpm = 0

        # 檢查 csv 是否存在
        csv_exists = os.path.exists('sensor_data.csv')

        # 用 HTML 顯示 BPM 與下載連結
        html = f'''
        <h2>目前 BPM：{bpm:.2f}</h2>
        {'<a href="/get_csv" download>點我下載 sensor_data.csv</a>' if csv_exists else '<p>尚未產生 CSV 檔案</p>'}
        '''
        return render_template_string(html)

    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/get_csv')
def get_csv():
    return send_file('sensor_data.csv', as_attachment=True)
# 啟動 Flask 應用
if __name__ == '__main__':
    initialize_csv()  # 初始化 CSV
    start_mqtt()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
