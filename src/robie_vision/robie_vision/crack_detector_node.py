import rclpy,cv2,numpy as np,yaml
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
C='/home/th0r12f4t/robie_ws/src/robie_vision/config/camera.yaml'
class CrackDetectorNode(Node):
 def __init__(self):
  super().__init__('crack_detector_node')
  with open(C) as f:g=yaml.safe_load(f)
  d=g['detection']
  self.min_area=float(d['min_area'])
  self.conf_thresh=float(d['confidence_threshold'])
  self.bridge=CvBridge()
  self.sub=self.create_subscription(
   Image,'/camera/image_raw',self.on_image,10)
  self.ev_pub=self.create_publisher(String,'/robie/event',10)
  self.an_pub=self.create_publisher(
   Image,'/camera/image_annotated',10)
  self.get_logger().info('crack detector ready')
 def on_image(self,msg):
  try:
   rgb=self.bridge.imgmsg_to_cv2(msg,desired_encoding='rgb8')
  except Exception as e:
   self.get_logger().error('bridge error: %s'%str(e))
   return
  gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
  th=cv2.adaptiveThreshold(
   gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
   cv2.THRESH_BINARY_INV,11,2)
  k=np.ones((3,3),np.uint8)
  cl=cv2.morphologyEx(th,cv2.MORPH_CLOSE,k,iterations=2)
  cl=cv2.morphologyEx(cl,cv2.MORPH_OPEN,k,iterations=1)
  edges=cv2.Canny(cl,50,150)
  contours,_=cv2.findContours(
   edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  annotated=rgb.copy()
  best=None
  for c in contours:
   area=cv2.contourArea(c)
   if area<self.min_area:
    continue
   x,y,w,h=cv2.boundingRect(c)
   ar=float(w)/float(h) if h>0 else 0.0
   conf=min(1.0,area/10000.0)
   if ar<0.1 or ar>10.0:
    conf=conf*0.5
   if conf<self.conf_thresh:
    continue
   nx=(x+w/2.0)/float(rgb.shape[1])
   ny=(y+h/2.0)/float(rgb.shape[0])
   if best is None or conf>best[0]:
    best=(conf,nx,ny)
   cv2.rectangle(annotated,(x,y),(x+w,y+h),(255,0,0),2)
  am=self.bridge.cv2_to_imgmsg(annotated,encoding='rgb8')
  am.header=msg.header
  self.an_pub.publish(am)
  if best is not None:
   em=String()
   em.data='C,%.2f,%.2f,%.2f'%best
   self.ev_pub.publish(em)
   self.get_logger().info('crack event: %s'%em.data)
def main(args=None):
 rclpy.init(args=args)
 n=CrackDetectorNode()
 try:
  rclpy.spin(n)
 except KeyboardInterrupt:
  pass
 finally:
  n.destroy_node()
  rclpy.shutdown()
if __name__=='__main__':
 main()
