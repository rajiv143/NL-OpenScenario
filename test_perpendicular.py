import math

# Ego position
ego_x, ego_y = -1.20, 111.88
ego_heading = -40.7  # degrees

# Crossing traffic position  
ct_x, ct_y = -7.41, 141.24

# Calculate angle to crossing traffic
dx = ct_x - ego_x
dy = ct_y - ego_y
angle_to_ct = math.degrees(math.atan2(dy, dx))

print(f"Ego position: ({ego_x}, {ego_y}), heading: {ego_heading}°")
print(f"Crossing traffic: ({ct_x}, {ct_y})")
print(f"Delta: dx={dx:.2f}, dy={dy:.2f}")
print(f"Angle from ego to crossing traffic: {angle_to_ct:.1f}°")
print(f"Ego heading: {ego_heading}°")

# Calculate angle difference
angle_diff = angle_to_ct - ego_heading
while angle_diff > 180:
    angle_diff -= 360
while angle_diff < -180:
    angle_diff += 360
    
print(f"Angle difference: {angle_diff:.1f}°")
print(f"Absolute angle difference: {abs(angle_diff):.1f}°")

if 60 <= abs(angle_diff) <= 120:
    print("This should be detected as PERPENDICULAR")
else:
    print("This is NOT perpendicular")
