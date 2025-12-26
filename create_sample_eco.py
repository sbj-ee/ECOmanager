from eco_manager import ECO
import os

# Initialize
if os.path.exists("sample_eco.db"):
    os.remove("sample_eco.db")
if os.path.exists("sample_report.md"):
    os.remove("sample_report.md")

eco = ECO("sample_eco.db")

# Create
print("Creating ECO...")
eco_id = eco.create_eco("Project Apollo", "Upgrade the main propulsion system for better efficiency.", "Dr. Stone")

# Add attachment
with open("specs.txt", "w") as f:
    f.write("Thrust: 5000kN\nISP: 450s")
eco.add_attachment(eco_id, "specs.txt", os.path.abspath("specs.txt"), "Dr. Stone")

# Submit
print("Submitting ECO...")
eco.submit_eco(eco_id, "Dr. Stone", "Ready for review.")

# Approve
print("Approving ECO...")
eco.approve_eco(eco_id, "Admin", "Approved for launch.")

# Generate Report
print("Generating Report...")
eco.generate_report(eco_id, "sample_report.md")

print("Done.")
