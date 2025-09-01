import json
from multiprocessing import Queue
from time import sleep
from typing import Any

import pyautogui


class Interpreter:
    def __init__(self, status_queue: Queue):
        # MP Queue to put current status of execution in while processes commands.
        # It helps us reflect the current status on the UI.
        self.status_queue = status_queue

    def process_commands(self, json_commands: list[dict[str, Any]]) -> bool:
        """
        Reads a list of JSON commands and runs the corresponding function call as specified in context.txt
        :param json_commands: List of JSON Objects with format as described in context.txt
        :return: True for successful execution, False for exception while interpreting or executing.
        """
        for command in json_commands:
            success = self.process_command(command)
            if not success:
                return False  # End early and return
        return True

    def process_command(self, json_command: dict[str, Any]) -> bool:
        """
        Reads the passed in JSON object and extracts relevant details. Format is specified in context.txt.
        After interpretation, it proceeds to execute the appropriate function call.

        :return: True for successful execution, False for exception while interpreting or executing.
        """
        function_name = json_command['function']
        parameters = json_command.get('parameters', {})
        human_readable_justification = json_command.get('human_readable_justification')
        print(f'Now performing - {function_name} - {parameters} - {human_readable_justification}')
        self.status_queue.put(human_readable_justification)
        try:
            self.execute_function(function_name, parameters)
            return True
        except Exception as e:
            print(f'\nError:\nWe are having a problem executing this step - {type(e)} - {e}')
            print(f'This was the json we received from the LLM: {json.dumps(json_command, indent=2)}')
            print(f'This is what we extracted:')
            print(f'\t function_name:{function_name}')
            print(f'\t parameters:{parameters}')

            return False

    def execute_function(self, function_name: str, parameters: dict[str, Any]) -> None:
        """
            We are expecting only two types of function calls below
            1. time.sleep() - to wait for web pages, applications, and other things to load.
            2. pyautogui calls to interact with system's mouse and keyboard.
        """
        # Sometimes pyautogui needs warming up i.e. sometimes first call isn't executed hence padding a random call here
        pyautogui.press("command", interval=0.2)
        
        # Add a small delay to ensure commands are processed
        sleep(0.1)

        # Clean function name - remove pyautogui. prefix if present
        if function_name.startswith("pyautogui."):
            function_name = function_name.replace("pyautogui.", "")
        elif function_name.startswith("time."):
            function_name = function_name.replace("time.", "")

        if function_name == "sleep" and (parameters.get("secs") or parameters.get("seconds")):
            sleep_time = parameters.get("secs") or parameters.get("seconds")
            sleep(sleep_time)
        elif hasattr(pyautogui, function_name):
            # Execute the corresponding pyautogui function i.e. Keyboard or Mouse commands.
            function_to_call = getattr(pyautogui, function_name)

            # Special handling for the 'write' function
            if function_name == 'write' and ('string' in parameters or 'text' in parameters or 'message' in parameters):
                # 'write' function expects a string, but LLM sometimes uses different parameter names
                string_to_write = parameters.get('string') or parameters.get('text') or parameters.get('message')
                interval = parameters.get('interval', 0.1)
                function_to_call(string_to_write, interval=interval)
            elif function_name == 'press' and ('keys' in parameters or 'key' in parameters):
                # 'press' can take a list of keys or a single key
                keys_to_press = parameters.get('keys') or parameters.get('key')
                presses = parameters.get('presses', 1)
                interval = parameters.get('interval', 0.2)
                if isinstance(keys_to_press, list):
                    # If it's a list, press each key individually
                    for key in keys_to_press:
                        function_to_call(key, presses=presses, interval=interval)
                else:
                    # Single key
                    function_to_call(keys_to_press, presses=presses, interval=interval)
            elif function_name == 'hotkey':
                # 'hotkey' function expects multiple key arguments
                if 'keys' in parameters:
                    # Handle case where LLM sends {"keys": ["command", "space"]}
                    keys = parameters['keys']
                    if isinstance(keys, list):
                        function_to_call(*keys)
                    else:
                        function_to_call(keys)
                else:
                    # Handle case where LLM sends individual key parameters
                    keys = list(parameters.values())
                    function_to_call(*keys)
            elif function_name == 'click':
                # Special handling for click function
                x = parameters.get('x')
                y = parameters.get('y')
                clicks = parameters.get('clicks', 1)
                if x is not None and y is not None:
                    print(f'Clicking at position ({x}, {y}) with {clicks} clicks')
                    function_to_call(x, y, clicks=clicks)
                else:
                    print(f'Invalid click parameters: {parameters}')
            else:
                # For other functions, pass the parameters as they are
                function_to_call(**parameters)
        else:
            print(f'No such function {function_name} in our interface\'s interpreter')
