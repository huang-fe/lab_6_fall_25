import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import sys
import os

# Import centralized API configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
from api_keys import get_openai_client, GPT_MODEL, MAX_TOKENS

# OpenAI client from centralized config
client = get_openai_client()

class GPT4ConversationNode(Node):
    def __init__(self):
        super().__init__('gpt4_conversation_node')

        # Create a subscriber to listen to user queries
        self.subscription = self.create_subscription(
            String,
            'user_query_topic',  # Replace with your topic name for queries
            self.query_callback,
            10
        )

        # Create a publisher to send back responses
        self.publisher_ = self.create_publisher(
            String,
            'gpt4_response_topic',  # Replace with your topic name for responses
            10
        )

        self.get_logger().info('GPT-4 conversation node started and waiting for queries...')

    def query_callback(self, msg):
        user_query = msg.data
        self.get_logger().info(f"Received user query: {user_query}")

        # Call GPT-4 API to get the response
        response = self.get_gpt4_response(user_query)

        # Publish the response to the ROS2 topic
        response_msg = String()
        response_msg.data = response
        self.publisher_.publish(response_msg)
        self.get_logger().info(f"Published GPT-4 response: {response}")

    def get_gpt4_response(self, query):
        try:
            # Making the API call to GPT using OpenAI's Python client
            response = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": query}
                ],
                max_tokens=MAX_TOKENS
            )

            # Extract the assistant's reply from the response
            gpt4_response = response.choices[0].message.content
            return gpt4_response

        except Exception as e:
            self.get_logger().error(f"Error calling GPT-4 API: {str(e)}")
            return "Sorry, I couldn't process your request due to an error."

def main(args=None):
    rclpy.init(args=args)

    # Create the node and spin it
    gpt4_conversation_node = GPT4ConversationNode()
    rclpy.spin(gpt4_conversation_node)

    # Clean up and shutdown
    gpt4_conversation_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
