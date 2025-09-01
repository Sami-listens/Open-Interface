"""
LangGraph Tools for Open Interface
"""
import json
import time
from typing import Dict, Any, List
from langchain_core.tools import StructuredTool
import pyautogui
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
from utils.screen import Screen


class PyAutoGUITools:
    """Collection of PyAutoGUI tools for LangGraph"""
    
    @staticmethod
    def click_tool(x: int, y: int, clicks: int = 1) -> str:
        """Click at specified coordinates"""
        try:
            pyautogui.click(x, y, clicks=clicks)
            return f"Clicked at ({x}, {y}) with {clicks} clicks"
        except Exception as e:
            return f"Click failed: {str(e)}"
    
    @staticmethod
    def type_text(text: str, interval: float = 0.05) -> str:
        """Type text with specified interval"""
        try:
            pyautogui.write(text, interval=interval)
            return f"Typed: {text}"
        except Exception as e:
            return f"Type failed: {str(e)}"
    
    @staticmethod
    def press_key(key, presses: int = 1) -> str:
        """Press a key or key combination"""
        try:
            if isinstance(key, list):
                pyautogui.hotkey(*key)
                return f"Pressed hotkey: {'+'.join(key)}"
            else:
                pyautogui.press(key, presses=presses)
                return f"Pressed key: {key} ({presses} times)"
        except Exception as e:
            return f"Key press failed: {str(e)}"
    
    @staticmethod
    def hotkey(*keys) -> str:
        """Press multiple keys as a hotkey combination"""
        try:
            pyautogui.hotkey(*keys)
            return f"Pressed hotkey: {'+'.join(keys)}"
        except Exception as e:
            return f"Hotkey failed: {str(e)}"
    
    @staticmethod
    def sleep_tool(seconds: float = 1.0) -> str:
        """Sleep for specified seconds"""
        time.sleep(seconds)
        return f"Slept for {seconds} seconds"
    
    @staticmethod
    def take_screenshot() -> str:
        """Take a screenshot and return base64 data"""
        try:
            screen = Screen()
            screenshot_data = screen.get_screenshot_in_base64()
            return f"Screenshot taken: {len(screenshot_data)} characters"
        except Exception as e:
            return f"Screenshot failed: {str(e)}"


def create_pyautogui_tools() -> List[StructuredTool]:
    """Create LangChain tools from PyAutoGUI functions"""
    
    tools = [
        StructuredTool.from_function(
            PyAutoGUITools.click_tool,
            name="click",
            description="Click at specified coordinates on screen"
        ),
        StructuredTool.from_function(
            PyAutoGUITools.type_text,
            name="type_text", 
            description="Type text with specified interval between characters"
        ),
        StructuredTool.from_function(
            PyAutoGUITools.press_key,
            name="press_key",
            description="Press a key or key combination (use list for hotkeys like ['cmd', 'space'])"
        ),
        StructuredTool.from_function(
            PyAutoGUITools.hotkey,
            name="hotkey",
            description="Press multiple keys as a hotkey combination (e.g., hotkey('cmd', 'space'))"
        ),
        StructuredTool.from_function(
            PyAutoGUITools.sleep_tool,
            name="sleep",
            description="Wait for specified number of seconds"
        ),
        StructuredTool.from_function(
            PyAutoGUITools.take_screenshot,
            name="take_screenshot",
            description="Take a screenshot of the current screen"
        )
    ]
    
    return tools
