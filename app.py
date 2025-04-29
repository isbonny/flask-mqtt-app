from flask import Flask, jsonify
import paho.mqtt.client as mqtt
import os
import json

# Flask 應用設定
app = Flask(__name__)

# MQTT 設定
MQTT_BROKER = 'broker.emqx.io'
MQTT_PORT = 1883
MQTT_TOPIC = '/imu_data'        # App 發送的資料主題
MQTT_PUB_TOPIC = '/result'  # 發佈計算後的平均值主題

# 儲存接收到的資料
sensor_data_list = []

# MQTT 連線成功的回調
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)

# MQTT 訊息處理回調（放寬格式檢查）
def on_message(client, userdata, msg):
    global sensor_data_list
    try:
        payload = msg.payload.decode('utf-8')
        print(f"Received message: {payload}")

        # 嘗試將訊息解碼為 JSON 格式
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON format, trying to parse as plain text: {payload}")
            # 如果 JSON 解析失敗，嘗試解析為字典格式
            data = {}
            # 這裡可以選擇用空字典或其他方式來處理錯誤格式數據

        # 如果收到的資料符合預期的結構，儲存進列表
        if isinstance(data, dict) and 'x' in data and 'y' in data and 'z' in data:
            sensor_data_list.append(data)
            print(f"Processed data: {data}")
        else:
            print(f"Warning: Missing expected keys ('x', 'y', 'z') in the data.")

        # 計算 (x + y + z) / 3 的平均值
        total = 0
        count = 0
        for d in sensor_data_list:
            total += (d['x'] + d['y'] + d['z']) / 3
            count += 1
        avg = round(total / count, 3)

        # 發佈計算結果到 MQTT
        client.publish(MQTT_PUB_TOPIC, str(avg))

    except Exception as e:
        print(f"Error processing message: {e}")

# MQTT 客戶端設置
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# 啟動 MQTT 客戶端
def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

# Flask 主頁面
@app.route('/')
def home():
    return 'Flask MQTT Average Server is Running!'

# 取得平均值 API
@app.route('/average')
def get_average():
    if not sensor_data_list:
        return jsonify({'average': None})

    total = 0
    count = 0
    for d in sensor_data_list:
        total += (d['x'] + d['y'] + d['z']) / 3
        count += 1

    avg = round(total / count, 3)
    return jsonify({'average': avg})

# 啟動 Flask 應用
if __name__ == '__main__':
    start_mqtt()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
