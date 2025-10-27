import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import pyttsx3
import karel  # Importing your KarelPupper API

class PupperCommandNode(Node):
    def __init__(self):
        super().__init__('pupper_command_node')

        # Create a subscriber to listen to user queries
        self.subscription = self.create_subscription(
            String,
            'user_query_topic',  # Topic name for user queries
            self.query_callback,
            10
        )

        # Create a publisher to send back responses
        self.publisher_ = self.create_publisher(
            String,
            'pupper_response_topic',  # Topic name for responses
            10
        )

        self.get_logger().info('Pupper Command Node has started and waiting for queries...')

        # Initialize the text-to-speech engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Set the speed of speech (optional)

        # Initialize KarelPupper robot control
        self.pupper = karel.KarelPupper()

    def query_callback(self, msg):
        user_query = msg.data
        self.get_logger().info(f"Received user query: {user_query}")

        # Directly process the response based on the user input
        response = self.process_user_command(user_query)

        # Publish the response to the ROS2 topic
        response_msg = String()
        response_msg.data = response
        self.publisher_.publish(response_msg)
        self.get_logger().info(f"Published Pupper response: {response}")

        # Play the response through the speaker
        self.play_response(response)

        # Execute robot commands based on the user input
        self.execute_robot_command(response)

    def process_user_command(self, query):
        """Process the user's query and return an appropriate command for the robot."""
        query = query.lower()

        # Check for keywords in the user query and return corresponding command
        if "go" in query:
            return "go"
        elif "left" in query:
            return "left"
        elif "turn left" in query:
            return "left"
        elif "turn right" in query:
            return "right"
        elif "right" in query:
            return "right"
        elif "up" in query:
            return "up"
        elif "stop" in query:
            return "stop"
        else:
            return "stop"  # Default to 'stop' if no valid command is found

    def play_response(self, response):
        try:
            # Use the TTS engine to say the response out loud
            self.tts_engine.say(response)
            self.tts_engine.runAndWait()
        except Exception as e:
            self.get_logger().error(f"Error playing response through speaker: {str(e)}")

    def execute_robot_command(self, response):
        """Execute the command on the robot based on the processed response."""
        self.get_logger().info(f"Executing command: {response}")
        if response == "go":
            self.pupper.move()
        elif response == "left":
            self.pupper.turn_left()
        elif response == "right":
            self.pupper.turn_right()
        elif response == "up":
            self.pupper.bark()
        elif response == "stop":
            self.pupper.stop()
        else:
            self.get_logger().info('No valid robot command found.')

def main(args=None):
    rclpy.init(args=args)

    # Create the node and spin it
    pupper_command_node = PupperCommandNode()
    rclpy.spin(pupper_command_node)

    # Clean up and shutdown
    pupper_command_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
