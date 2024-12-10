#!/bin/bash

# Get the current time and store it in a variable
current_time=$(date "+%Y-%m-%d %H:%M:%S")

# Print the current time to the log
echo "Script started at: $current_time" >> /home/differenz83/Documents/AI_Internal_Chatbot/chatbot_pgvector/bash_files/logs/inventory_operations.log

# Change to the desired directory (if needed)
cd /home/differenz83/Documents/AI_Internal_Chatbot/chatbot_pgvector

# Activate the virtual environment
source .python3.10/bin/activate

# Change to the src directory
cd src

# Run the Python script and log both stdout and stderr to the log file
python inventory_operations.py >> /home/differenz83/Documents/AI_Internal_Chatbot/chatbot_pgvector/bash_files/logs/inventory_operations.log 2>&1

# Log the end time
end_time=$(date "+%Y-%m-%d %H:%M:%S")
echo "Script finished at: $end_time" >> /home/differenz83/Documents/AI_Internal_Chatbot/chatbot_pgvector/bash_files/logs/inventory_operations.log

