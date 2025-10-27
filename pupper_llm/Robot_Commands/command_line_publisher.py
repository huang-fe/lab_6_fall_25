import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class CommandLinePublisher(Node):
    def __init__(self):
        super().__init__('command_line_publisher')

        # Create a publisher for the user query topic
        self.publisher_ = self.create_publisher(
            String,
            'user_query_topic',  # Replace with the topic name used in your GPT-4 node
            10
        )
        self.get_logger().info('Command Line Publisher Node has started.')

    def publish_message(self, message):
        # Create a String message and publish it
        msg = String()
        msg.data = message
        self.publisher_.publish(msg)
        self.get_logger().info(f"Published message: {message}")


def main(args=None):
    rclpy.init(args=args)

    # Create the command line publisher node
    command_publisher = CommandLinePublisher()

    # Keep taking user input and publish it
    try:
        while rclpy.ok():
            # Get input from the user
            user_input = input("Enter a command for GPT-4: ")

            # Publish the input
            if user_input.lower() == 'exit':
                print("Exiting the publisher.")
                break

            command_publisher.publish_message(user_input)

            # Allow ROS2 to process the message
            rclpy.spin_once(command_publisher, timeout_sec=0.1)

    except KeyboardInterrupt:
        print("Interrupted by user. Exiting...")

    # Clean up and shutdown
    command_publisher.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
