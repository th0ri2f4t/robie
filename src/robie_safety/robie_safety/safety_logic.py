class SafetyInterlock:
    """
    Pure Python state machine for the R.O.B.I.E. safety interlock.
    Determines if the motors are allowed to spin based on hardware inputs.
    """
    def __init__(self):
        self.estop_pressed = False
        self.bumper_front = False
        self.bumper_rear = False
        self.rf_link_alive = False
        self.motor_command = False

    def update(self, estop: bool, bumper_front: bool, bumper_rear: bool, rf_alive: bool):
        """Update the sensor states and evaluate the interlock."""
        self.estop_pressed = estop
        self.bumper_front = bumper_front
        self.bumper_rear = bumper_rear
        self.rf_link_alive = rf_alive
        
        # The Golden Rule: Motors are ONLY enabled if E-stop is clear, 
        # RF is alive, and bumpers are clear.
        if self.estop_pressed:
            self.motor_command = False
        elif not self.rf_link_alive:
            self.motor_command = False
        elif self.bumper_front or self.bumper_rear:
            self.motor_command = False
        else:
            self.motor_command = True
            
        return self.motor_command

    def get_state_summary(self) -> dict:
        return {
            'estop': self.estop_pressed,
            'bumper_front': self.bumper_front,
            'bumper_rear': self.bumper_rear,
            'rf_alive': self.rf_link_alive,
            'motors_enabled': self.motor_command
        }
