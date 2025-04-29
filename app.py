from flask import Flask, jsonify
import paho.mqtt.client as mqtt
import os
import json

# 建立 Flask 應用
app = Flask(__name__)

# MQTT 設定
MQTT_BROKER = 'broker.emqx.io'
MQTT_PORT = 1883
MQTT_SUB_TOPIC = '/imu_data'        # App 發送數據的主題
MQTT_PUB_TOPIC = '/result'     # Flask 回傳平均值的主題

# 用來累積收到的感測器資料
sensor_data_list = []

# MQTT 連線成功後訂閱主題
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe(MQTT_SUB_TOPIC)

# 當收到 MQTT 訊息時執行的處理邏輯
def on_message(client, userdata, msg):
    global sensor_data_list
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        if all(k in data for k in ('x', 'y', 'z')):
            sensor_data_list.append(data)

            # 計算 (x + y + z) / 3 的平均值
            total = sum((d['x'] + d['y'] + d['z']) / 3 for d in sensor_data_list)
            count = len(sensor_data_list)
            avg = round(total / count, 3)

            # 發送平均值到 MQTT
            client.publish(MQTT_PUB_TOPIC, str(avg))

            print(f"[MQTT] Received: {data}, Published average: {avg}")

    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")

# 建立 MQTT 客戶端
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
    return 'Flask MQTT Average Server is Running!'

# Flask 應用啟動
if __name__ == '__main__':
    start_mqtt()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
