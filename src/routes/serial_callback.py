class SerialCallback:
    """Interface for serial connection callbacks, matching desktop SerialCallback.java"""
    
    def on_socket_closed(self):
        """Called when serial connection is closed"""
        pass