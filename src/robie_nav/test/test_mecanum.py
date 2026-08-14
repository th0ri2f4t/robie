from robie_nav.mecanum_driver import inverse_kinematics

R = 0.032
ARM = 0.18

def test_forward_all_equal():
    w = inverse_kinematics(0.2, 0.0, 0.0, R, ARM)
    assert all(abs(x - 0.2 / R) < 1e-6 for x in w)

def test_strafe_left_pattern():
    fl, fr, rl, rr = inverse_kinematics(0.0, 0.2, 0.0, R, ARM)
    assert fl < 0 and fr > 0 and rl > 0 and rr < 0

def test_rotate_ccw_pattern():
    fl, fr, rl, rr = inverse_kinematics(0.0, 0.0, 1.0, R, ARM)
    # CCW rotation: Front/Left go backward (-), Front/Right go forward (+)
    assert fl < 0 and fr > 0 and rl < 0 and rr > 0

def test_linearity():
    w1 = inverse_kinematics(1.0, 0.0, 0.0, R, ARM)
    w2 = inverse_kinematics(2.0, 0.0, 0.0, R, ARM)
    assert all(abs(w2[i] - 2 * w1[i]) < 1e-6 for i in range(4))
