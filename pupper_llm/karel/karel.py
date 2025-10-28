# karel.py
import time
import os
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import simpleaudio as sa
import pygame

class KarelPupper:
    def start():
        if not rclpy.ok():
            rclpy.init()

    def __init__(self):
        if not rclpy.ok():
            rclpy.init()
        self.node = Node('karel_node')
        self.publisher = self.node.create_publisher(Twist, 'cmd_vel', 10)

    def move(self, linear_x, linear_y, angular_z):
        move_cmd = Twist()
        move_cmd.linear.x = linear_x
        move_cmd.linear.y = linear_y
        move_cmd.angular.z = angular_z
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Move...')
        self.stop()
    
    def wiggle(self):

        move_cmd = Twist()
        wiggle_width = 0.3
        total_wiggle_time = 3.6
        direction = 1
    
        start_time = time.time()
        while time.time() - start_time < total_wiggle_time:
            if (direction):
                self.turn_right()
                time.sleep(wiggle_width)
                direction = 0
            else:
                self.turn_left()
                time.sleep(wiggle_width)
                direction = 1
            
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Wwwwwwiiiiigggggllllleeeee')
        self.stop()

    def move_forward(self):
        move_cmd = Twist()
        move_cmd.linear.x = 1.0
        move_cmd.angular.z = 0.0 
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Move forward...')
        self.stop()
    
    def move_backward(self):
        ################################################################################################
        # TODO: Implement move_backward method
        ################################################################################################
        move_cmd = Twist()
        move_cmd.linear.x = -1.0
        move_cmd.angular.z = 0.0 
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Move backward...')
        self.stop()

    def move_left(self):
        ################################################################################################
        # TODO: Implement move_left method
        ################################################################################################
        move_cmd = Twist()
        move_cmd.linear.y = -1.0
        move_cmd.angular.z = 0.0 
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Move Left...')
        self.stop()

    
    def move_right(self):
        ################################################################################################
        # TODO: Implement move_right method
        ################################################################################################
        move_cmd = Twist()
        move_cmd.linear.y = 1.0
        move_cmd.angular.z = 0.0 
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Move Right...')
        self.stop()

    
    def turn_left(self):
        ################################################################################################
        # TODO: Implement turn_left method
        ################################################################################################
        move_cmd = Twist()
        move_cmd.linear.x = 0.0
        move_cmd.angular.z = -0.8
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Turn Left...')
        self.stop()


    def turn_right(self):
        ################################################################################################
        # TODO: Implement turn_right method
        ################################################################################################
        move_cmd = Twist()
        move_cmd.linear.x = 0.0
        move_cmd.angular.z = 0.8
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
        self.node.get_logger().info('Turn Right...')
        self.stop()


    def bark(self):
        self.node.get_logger().info('Bark...')
        pygame.mixer.init()
        
        # Directory-independent path to sound file
        # Get the directory of this file, then navigate to sounds directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sounds_dir = os.path.join(current_dir, '..', '..', 'sounds')
        bark_sound_path = os.path.join(sounds_dir, 'dog_bark.wav')
        
        # Normalize the path to handle .. properly
        bark_sound_path = os.path.normpath(bark_sound_path)
        
        try:
            if os.path.exists(bark_sound_path):
                bark_sound = pygame.mixer.Sound(bark_sound_path)
                bark_sound.play()
                self.node.get_logger().info(f'Playing bark sound from: {bark_sound_path}')
            else:
                self.node.get_logger().warning(f'Bark sound file not found at: {bark_sound_path}')
                # Fallback - just log the bark
                self.node.get_logger().info('WOOF WOOF! (sound file not found)')
        except Exception as e:
            self.node.get_logger().error(f'Error playing bark sound: {e}')
            self.node.get_logger().info('WOOF WOOF! (sound playback failed)')
        
        self.stop()


    def stop(self):
        self.node.get_logger().info('Stopping...')
        move_cmd = Twist()
        move_cmd.linear.x = 0.0
        move_cmd.linear.y = 0.0
        move_cmd.linear.z = 0.0
        move_cmd.angular.x = 0.0
        move_cmd.angular.y = 0.0
        move_cmd.angular.z = 0.0
        self.publisher.publish(move_cmd)
        rclpy.spin_once(self.node, timeout_sec=1.0)
    
    def __del__(self):
        self.node.get_logger().info('Tearing down...')
        self.node.destroy_node()
        rclpy.shutdown()
