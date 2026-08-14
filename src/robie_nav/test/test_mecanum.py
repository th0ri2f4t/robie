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
    assert fl < 0 and fr > 0 and rl > 0 and rr < 0


def test_clamping_preserves_ratio():
    w = inverse_kinematics(5.0, 0.0, 0.0, R, ARM)  # absurd speed
    assert max(abs(x) for x in w) <= 30.0 + 1e-6
