import subprocess,time,rclpy,cv2,yaml
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
C='/home/th0r12f4t/robie_ws/src/robie_vision/config/camera.yaml'
class CameraNode(Node):
 def __init__(self):
  super().__init__('camera_node')
  with open(C) as f:g=yaml.safe_load(f)
  c,s=g['camera'],g['stream']
  self.bridge=CvBridge()
  self.pub=self.create_publisher(Image,'/camera/image_raw',10)
  p=int(s['port'])
  cmd=(['rpicam-vid','-t','0','-n','--codec','mjpeg']
  +['--width',str(c['width']),'--height',str(c['height'])]
  +['--framerate',str(c['framerate']),'--quality',str(c['quality'])]
  +['--denoise',str(c['denoise']),'--flush','--listen']
  +['-o','tcp://0.0.0.0:'+str(p)])
  self.proc=subprocess.Popen(cmd)
  self.get_logger().info('started rpicam-vid on port %d'%p)
  time.sleep(3.0)
  self.cap=cv2.VideoCapture('tcp://127.0.0.1:'+str(p))
  if not self.cap.isOpened():
   self.get_logger().error('cannot open camera stream')
  else:
   self.get_logger().info('camera stream open')
  self.create_timer(1.0/max(1.0,float(c['framerate'])),self.tick)
 def tick(self):
  if not self.cap.isOpened():
   return
  ok,fr=self.cap.read()
  if not ok:
   self.get_logger().warn('frame read failed')
   return
  rgb=cv2.cvtColor(fr,cv2.COLOR_BGR2RGB)
  m=self.bridge.cv2_to_imgmsg(rgb,encoding='rgb8')
  m.header.stamp=self.get_clock().now().to_msg()
  m.header.frame_id='camera_frame'
  self.pub.publish(m)
 def destroy_node(self):
  try:
   self.cap.release()
  except Exception:
   pass
  try:
   self.proc.terminate()
  except Exception:
   pass
  super().destroy_node()
def main(args=None):
 rclpy.init(args=args)
 n=CameraNode()
 try:
  rclpy.spin(n)
 except KeyboardInterrupt:
  pass
 finally:
  n.destroy_node()
  rclpy.shutdown()
if __name__=='__main__':
 main()
