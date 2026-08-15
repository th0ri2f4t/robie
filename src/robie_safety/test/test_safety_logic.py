from robie_safety.safety_logic import SafetyInterlock

def test_initial_state_is_safe():
    logic = SafetyInterlock()
    logic.update(False, False, False, False)
    assert logic.motor_command is False, "Motors must default to DISABLED"

def test_all_clear_enables_motors():
    logic = SafetyInterlock()
    enabled = logic.update(False, False, False, True)
    assert enabled is True, "Motors should enable when all systems are green"

def test_estop_kills_motors():
    logic = SafetyInterlock()
    logic.update(False, False, False, True)  # Start enabled
    enabled = logic.update(True, False, False, True) # Press E-stop
    assert enabled is False, "E-STOP MUST CUT POWER"

def test_rf_loss_kills_motors():
    logic = SafetyInterlock()
    logic.update(False, False, False, True)  # Start enabled
    enabled = logic.update(False, False, False, False) # Lose RF
    assert enabled is False, "RF loss must cut power"

def test_bumper_kills_motors():
    logic = SafetyInterlock()
    logic.update(False, False, False, True)  # Start enabled
    enabled = logic.update(False, True, False, True) # Hit front bumper
    assert enabled is False, "Bumper hit must cut power"

def test_estop_overrides_everything():
    logic = SafetyInterlock()
    # Even if we try to trick it by clearing the other faults, 
    # the E-stop must remain the absolute master override.
    enabled = logic.update(True, False, False, True) 
    assert enabled is False
