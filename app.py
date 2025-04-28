from flask import Flask, jsonify
import paho.mqtt.client as mqtt

# Flask 應用
app = Flask(__name__)

# MQTT 配置
MQTT_BROKER = 'broker.emqx.io'  # 這是我們的公共 MQTT 代理
MQTT_PORT = 1883
MQTT_TOPIC = '/imu_data'  # 訂閱感測器數據的主題

# 用來存儲接收到的數據
sensor_data = {}

# MQTT 連接回調
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)  # 訂閱 MQTT 主題

# MQTT 消息處理回調
def on_message(client, userdata, msg):
    global sensor_data
    # 將接收到的消息解碼並轉換為 JSON
    sensor_data = msg.payload.decode('utf-8')
    print(f"Received message: {sensor_data}")

# 設置 MQTT 客戶端
mqtt_client = mqtt.Client()

# 設置回調函數
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# 啟動 MQTT 客戶端並連接
def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()  # 開啟 MQTT 事件處理循環

@app.route('/')
def home():
    return 'Flask is running with MQTT!'

@app.route('/sensor_data')
def get_sensor_data():
    return jsonify(sensor_data)

# 啟動 Flask 應用和 MQTT 客戶端
if __name__ == '__main__':
    start_mqtt()
    port = int(os.environ.get('PORT', 5000))  # 取得 Render 給的 PORT 環境變數，找不到就預設 5000
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
