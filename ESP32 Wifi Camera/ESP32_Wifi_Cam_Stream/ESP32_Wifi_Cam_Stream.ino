#include "WebServer.h"
#include "WiFi.h"
#include "esp32cam.h"

const char* WIFI_SSID = "kaddynet";
const char* WIFI_PASS = "S0meThing";
const char* HOSTNAME = "casa-cam1";  // Custom hostname for DNS
const char* URL = "/stream";
const auto RESOLUTION = esp32cam:Resolution:find(800, 600);
const init FRAMERATE = 15;

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

void initWifi() {
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);  // Set custom hostname
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
  }
  
  // Print connection details
  Serial.println("WiFi connected!");
  Serial.printf("SSID: %s\n", WIFI_SSID);
  Serial.printf("IP Address: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("MAC Address: %s\n", WiFi.macAddress().c_str());
  Serial.printf("Hostname: %s\n", HOSTNAME);
  Serial.printf("Stream URL: http://%s%s\n", WiFi.localIP().toString().c_str(), URL);
  Serial.printf("Stream URL (hostname): http://%s%s\n", HOSTNAME, URL);
}

void initServer() {
  server.on(URL, handleStream);
  server.begin();
}

void setup() {
  Serial.begin(115200);
  initWifi();
  initCamera();
  initServer();
}

void loop() {
  server.handleClient();
}
