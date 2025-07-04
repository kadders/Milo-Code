#include "WebServer.h"
#include "WiFi.h"
#include "esp32cam.h"

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* HOSTNAME = "casa-cam1";  // Custom hostname for DNS
const char* URL = "/stream";
const auto RESOLUTION = esp32cam:Resolution:find(800, 600);
const init FRAMERATE = 15;
const int WIFI_TIMEOUT_MS = 30000;  // 30 seconds timeout
const int WIFI_RETRY_DELAY_MS = 1000;  // 1 second between retries

WebServer server(80);

void handleStream() {
  static char head[128];
  WiFiClient client = server.client();

  server.sendContent("HTTP/1.1 200 OK\r\n"
                     "Content-Type: multipart/x-mixed-replace; "
                     "boundary=frame\r\n\r\n");

  while (client.connected()) {
    auto frame = esp32cam::capture();
    if (frame) {
      sprintf(head,
              "--frame\r\n"
              "Content-Type: image/jpeg\r\n"
              "Content-Length: %ul\r\n\r\n",
              frame->size());
      client.write(head, strlen(head));
      frame->writeTo(client);
      client.write("\r\n");
      delay(1000 / FRAMERATE);
    }
  }
}

void initCamera() {
  using namespace esp32cam;
  Config cfg;
  cfg.setPins(pins::XiaoSense);
  cfg.setResolution(RESOLUTION);
  cfg.setBufferCount(2);
  cfg.setJpeg(80);
  Camera.begin(cfg);
}

bool initWifi() {
  Serial.println("Connecting to WiFi...");
  Serial.printf("SSID: %s\n", WIFI_SSID);
  
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);  // Set custom hostname
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  unsigned long startTime = millis();
  int attempts = 0;
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(WIFI_RETRY_DELAY_MS);
    attempts++;
    
    // Check for timeout
    if (millis() - startTime > WIFI_TIMEOUT_MS) {
      Serial.println("WiFi connection timeout!");
      Serial.printf("Failed after %d attempts\n", attempts);
      return false;
    }
    
    // Show progress every 5 seconds
    if (attempts % 5 == 0) {
      Serial.printf("Still trying to connect... (attempt %d)\n", attempts);
    }
  }
  
  // Print connection details
  Serial.println("WiFi connected!");
  Serial.printf("SSID: %s\n", WIFI_SSID);
  Serial.printf("IP Address: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("MAC Address: %s\n", WiFi.macAddress().c_str());
  Serial.printf("Hostname: %s\n", HOSTNAME);
  Serial.printf("Stream URL: http://%s%s\n", WiFi.localIP().toString().c_str(), URL);
  Serial.printf("Stream URL (hostname): http://%s%s\n", HOSTNAME, URL);
  
  return true;
}

void initServer() {
  server.on(URL, handleStream);
  server.begin();
}

void setup() {
  Serial.begin(115200);
  Serial.println("ESP32 Camera Stream Starting...");
  
  if (!initWifi()) {
    Serial.println("Failed to connect to WiFi. Restarting in 10 seconds...");
    delay(10000);
    ESP.restart();
  }
  
  initCamera();
  initServer();
  Serial.println("Setup complete! Camera stream is ready.");
}

void loop() {
  server.handleClient();
}
