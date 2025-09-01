"""
Simple UI for LangGraph-based Open Interface
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from typing import Optional

try:
    from .graph import OpenInterfaceGraph
except ImportError:
    # Handle direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from langgraph_interface.graph import OpenInterfaceGraph


class SimpleOpenInterfaceUI:
    """Simple UI for the LangGraph-based Open Interface"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Open Interface - LangGraph")
        self.root.geometry("600x500")
        
        self.graph = None
        self.execution_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        self._setup_ui()
        self._initialize_graph()
    
    def _setup_ui(self):
        """Setup the UI components"""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Open Interface - LangGraph", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Input section
        input_label = ttk.Label(main_frame, text="Enter your request:")
        input_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        self.input_entry = ttk.Entry(main_frame, font=("Arial", 12))
        self.input_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5), padx=(10, 0))
        self.input_entry.bind('<Return>', lambda e: self._execute_request())
        
        # Execute button
        self.execute_button = ttk.Button(main_frame, text="Execute", 
                                        command=self._execute_request)
        self.execute_button.grid(row=1, column=2, pady=(0, 5), padx=(10, 0))
        
        # Output section
        output_label = ttk.Label(main_frame, text="Execution Log:")
        output_label.grid(row=2, column=0, sticky=(tk.W, tk.N), pady=(10, 5))
        
        self.output_text = scrolledtext.ScrolledText(main_frame, height=20, width=70,
                                                    font=("Consolas", 10))
        self.output_text.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), 
                             pady=(10, 5), padx=(10, 0))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                     command=self._stop_execution, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_button = ttk.Button(button_frame, text="Clear", 
                                      command=self._clear_output)
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.grid(row=4, column=0, columnspan=3, pady=(10, 0))
    
    def _initialize_graph(self):
        """Initialize the LangGraph"""
        try:
            self.graph = OpenInterfaceGraph()
            self._log("LangGraph initialized successfully")
            self.status_var.set("Ready - LangGraph initialized")
        except Exception as e:
            self._log(f"Failed to initialize LangGraph: {str(e)}")
            self.status_var.set("Error - Failed to initialize")
            messagebox.showerror("Initialization Error", 
                               f"Failed to initialize LangGraph:\n{str(e)}")
    
    def _execute_request(self):
        """Execute the user request"""
        if not self.graph:
            messagebox.showerror("Error", "LangGraph not initialized")
            return
        
        user_request = self.input_entry.get().strip()
        if not user_request:
            messagebox.showwarning("Warning", "Please enter a request")
            return
        
        if self.is_running:
            messagebox.showwarning("Warning", "Execution already in progress")
            return
        
        # Start execution in a separate thread
        self.execution_thread = threading.Thread(
            target=self._run_execution, 
            args=(user_request,)
        )
        self.execution_thread.daemon = True
        self.execution_thread.start()
    
    def _run_execution(self, user_request: str):
        """Run the execution in a separate thread"""
        self.is_running = True
        self.execute_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("Executing...")
        
        try:
            self._log(f"Starting execution: {user_request}")
            
            # Stream the execution
            for chunk in self.graph.stream_execution(user_request):
                if not self.is_running:  # Check for stop request
                    break
                
                self._log(f"Chunk: {chunk}")
                
                # Update UI in main thread
                self.root.after(0, self._update_status, chunk)
            
            if self.is_running:
                self._log("Execution completed successfully")
                self.status_var.set("Ready - Execution completed")
            else:
                self._log("Execution stopped by user")
                self.status_var.set("Ready - Execution stopped")
                
        except Exception as e:
            self._log(f"Execution failed: {str(e)}")
            self.status_var.set("Error - Execution failed")
            messagebox.showerror("Execution Error", f"Execution failed:\n{str(e)}")
        
        finally:
            self.is_running = False
            self.execute_button.config(state="normal")
            self.stop_button.config(state="disabled")
    
    def _stop_execution(self):
        """Stop the current execution"""
        if self.is_running:
            self.is_running = False
            self._log("Stop requested...")
            self.status_var.set("Stopping...")
    
    def _clear_output(self):
        """Clear the output text"""
        self.output_text.delete(1.0, tk.END)
    
    def _log(self, message: str):
        """Log a message to the output"""
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def _update_status(self, chunk):
        """Update status based on execution chunk"""
        if chunk.get("is_complete"):
            if chunk.get("error_message"):
                self.status_var.set(f"Error: {chunk['error_message']}")
            else:
                self.status_var.set("Ready - Task completed")
    
    def run(self):
        """Run the UI"""
        self.root.mainloop()


def main():
    """Main function to run the simple UI"""
    app = SimpleOpenInterfaceUI()
    app.run()


if __name__ == "__main__":
    main()
