# Required PostgreSQL Tables:
# The script will check if tables exist and are conformant.
# If not, it will create missing tables.
# If tables exist and are conformant, the script will propose to flush tables before starting.
#
# CREATE TABLE IF NOT EXISTS users (
#     user_id VARCHAR(255) PRIMARY KEY,
#     first_name VARCHAR(255),
#     last_name VARCHAR(255),
#     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
# );
# CREATE TABLE IF NOT EXISTS sessions (
#     session_id VARCHAR(255) PRIMARY KEY,
#     user_id VARCHAR(255) REFERENCES users(user_id),
#     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
# );
# CREATE TABLE IF NOT EXISTS messages (
#     message_id SERIAL PRIMARY KEY,
#     session_id VARCHAR(255) REFERENCES sessions(session_id),
#     role VARCHAR(50), -- 'user' or 'assistant'
#     content TEXT,
#     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
# );

import re # Import the regex module
import uuid
from autogen import UserProxyAgent, ConversableAgent # Use standard ConversableAgent
from llm_config import config_list
from prompt import agent_system_message
from util import generate_user_id
import streamlit as st
import psycopg2
#import traceback # Import traceback for detailed error logging

# Import PostgreSQL configurations from pgsql_config.py
from pgsql_config import DB_URI


def check_and_setup_db():
    """Checks if required tables exist and creates them if necessary."""
    print("--- Checking and setting up database tables ---")
    required_tables = {
        "users": ["user_id", "first_name", "last_name", "created_at"],
        "sessions": ["session_id", "user_id", "created_at"],
        "messages": ["message_id", "session_id", "role", "content", "created_at"],
    }
    success, conn, cursor = initialize_postgresql_client()
    if not success:
        st.error("Failed to connect to database for setup.")
        return False

    try:
        db_ok = True
        for table, columns in required_tables.items():
            # Check if table exists
            cursor.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table}');")
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                print(f"--- Table '{table}' does not exist. Creating... ---")
                db_ok = False # Mark database as not fully set up yet
                if table == "users":
                    create_sql = """
                    CREATE TABLE users (
                        user_id VARCHAR(255) PRIMARY KEY,
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );"""
                elif table == "sessions":
                    create_sql = """
                    CREATE TABLE sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) REFERENCES users(user_id),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );"""
                elif table == "messages":
                    create_sql = """
                    CREATE TABLE messages (
                        message_id SERIAL PRIMARY KEY,
                        session_id VARCHAR(255) REFERENCES sessions(session_id),
                        role VARCHAR(50), -- 'user' or 'assistant'
                        content TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );"""
                cursor.execute(create_sql)
                print(f"--- Table '{table}' created. ---")
            else:
                # Check if columns exist and are conformant (basic check)
                cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{table}';")
                existing_columns = [row[0] for row in cursor.fetchall()]
                missing_columns = [col for col in columns if col not in existing_columns]

                if missing_columns:
                    print(f"--- Table '{table}' is missing columns: {missing_columns}. Please update schema manually. ---")
                    st.error(f"Database table '{table}' is missing required columns. Please update your database schema.")
                    db_ok = False # Database is not conformant
                else:
                    print(f"--- Table '{table}' exists and columns look conformant. ---")

        if db_ok:
            print("--- Database schema check passed. All required tables/columns found. ---")
            return True # Database is ready
        else:
            st.warning("Database schema issues found or tables created. Please check terminal for details.")
            return False # Database was not fully ready

    except Exception as e:
        print(f"--- Error during database setup: {e} ---")
        st.error(f"An error occurred during database setup: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def initialize_postgresql_client():
    """Initialize the PostgreSQL client and return connection and cursor."""
    print("Attempting to initialize PostgreSQL client...") # Added print
    conn = None
    cursor = None
    try:
        # Add a connection timeout (e.g., 5 seconds)
        conn = psycopg2.connect(DB_URI, connect_timeout=5)
        conn.autocommit = True # Set autocommit to simplify transaction handling for this app
        cursor = conn.cursor()
        print("PostgreSQL client initialized successfully.") # Added print
        # st.sidebar.success("PostgreSQL Client Initialized Successfully.") # Move success message to initialize_session
        return True, conn, cursor # Return connection as well
    except Exception as e:
        print(f"Error initializing PostgreSQL client: {e}") # Added print
        st.error(f"Failed to initialize PostgreSQL Client: {e}")
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return False, None, None


def persist_message_to_db(session_id, role, content):
    """Persist a message to the PostgreSQL database."""
    success, conn, cursor = initialize_postgresql_client()
    if not success:
        st.error("Failed to connect to DB for persisting message.")
        return

    try:
        add_message_query = """
        INSERT INTO messages (session_id, role, content)
        VALUES (%s, %s, %s)
        """
        cursor.execute(add_message_query, (session_id, role, content))
        # No need to commit if autocommit is True
    except Exception as e:
        print(f"--- Error persisting message to DB: {e} ---") # Added print
        st.error(f"Failed to persist message to DB: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def initialize_session(first_name, last_name):
    """Initialize the session state and PostgreSQL connection."""
    print(f"--- initialize_session called for {first_name} {last_name} ---") # MOVED & UPDATED PRINT
    # Removed check for global zep

    if "zep_session_id" not in st.session_state:
        print("--- 'zep_session_id' not in session_state, proceeding ---") # ADDED PRINT
        user_id = generate_user_id(first_name, last_name)

        # Streamlit session state
        session_id = str(uuid.uuid4())
        st.session_state.zep_session_id = session_id # Keep name for compatibility for now
        st.session_state.zep_user_id = user_id       # Keep name for compatibility for now
        st.session_state.messages = []               # Store chat history for display
        st.session_state.first_name = first_name     # Store names for potential use
        st.session_state.last_name = last_name

        conn = None
        cursor = None
        try:
            # Removed Zep fact rating definitions

            # Attempt to connect to PostgreSQL and manage user data
            is_connection_successful, conn, cursor = initialize_postgresql_client()
            if is_connection_successful:
                print("DB connection successful for session init.") # Added print
                st.sidebar.success("PostgreSQL Client Initialized Successfully.") # Show success message here

                # --- DIAGNOSTIC: Check table columns ---
                try:
                    print("--- Querying information_schema for 'users' table columns ---")
                    check_cols_query = "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users';"
                    cursor.execute(check_cols_query)
                    columns = cursor.fetchall()
                    print(f"--- Columns found in 'public.users': {columns} ---")
                except Exception as diag_e:
                    print(f"--- Error querying information_schema: {diag_e} ---")
                # --- END DIAGNOSTIC ---

                # Create or update user
                print("Creating/updating user...") # Added print
                create_user_query = """
                INSERT INTO users (user_id, first_name, last_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name;
                """
                cursor.execute(create_user_query, (user_id, first_name, last_name))
                print("User created/updated.") # Added print

                # Create session
                print("Creating session...") # Added print
                add_session_query = """
                INSERT INTO sessions (session_id, user_id)
                VALUES (%s, %s);
                """
                cursor.execute(add_session_query, (session_id, user_id))
                print("Session created.") # Added print

                st.sidebar.info(f"Session initialized for {first_name} {last_name}.")
                st.session_state.chat_initialized = True # Set flag to True on success
                print("Session initialization complete. Rerunning.") # Added print
                st.rerun() # Rerun to update the main interface

            else:
                print("DB connection failed during session init.") # Added print
                st.error("❌ Failed to initialize PostgreSQL client during session setup.")
                st.session_state.chat_initialized = False

        except Exception as e:
            print(f"--- Error during session init DB operations: {e} ---") # ADDED PRINT
            st.error(f"Failed during PostgreSQL user/session initialization: {e}")
            st.session_state.chat_initialized = False
            # st.stop() # Avoid stopping the app abruptly

        finally:
            print("--- Closing DB connection/cursor in initialize_session finally block ---") # ADDED PRINT
            # Ensure cursor and connection are closed
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        print("--- Session already initialized, skipping ---") # ADDED PRINT


def create_agents():
    """Create and configure the conversational agents."""
    print("Attempting to create agents...") # Added print
    # Check if chat_initialized is True before creating agents
    if st.session_state.get("chat_initialized", False):
        print("Chat initialized, proceeding with agent creation.") # Added print
        try: # Add try-except around agent creation
            # Use standard ConversableAgent
            print("Creating ConversableAgent (AssistantAgent)...") # Added print
            agent = ConversableAgent(
                name="AssistantAgent", # More descriptive name
                system_message=agent_system_message,
                llm_config={"config_list": config_list},
                # zep_session_id=st.session_state.zep_session_id, # Removed - Not a parameter for standard ConversableAgent
                # min_fact_rating=0.7, # Removed - Requires Zep backend
                function_map=None,
                human_input_mode="NEVER",
                # is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"), # Example termination condition
            )
            print("ConversableAgent created.") # Added print

            # Create UserProxyAgent
            print("Creating UserProxyAgent...") # Added print
            user = UserProxyAgent(
                name="UserProxy",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=0, # Important: Set to 0 if user proxy shouldn't reply automatically
                code_execution_config=False,  # No code execution
                llm_config=False,             # No LLM for the proxy
                # is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            )
            print("UserProxyAgent created.") # Added print
            print("Agent creation successful.") # Added print
            return agent, user
        except Exception as e:
            print(f"Error creating agents: {e}") # Added print
            st.error(f"Failed to create agents: {e}")
            return None, None
    else:
        print("Chat not initialized, skipping agent creation.") # Added print
        # Return None if chat is not initialized
        return None, None


def handle_conversations(agent: ConversableAgent, user: UserProxyAgent, prompt: str):
    """Process user input, generate responses, and persist messages."""
    session_id = st.session_state.zep_session_id

    # Add user message to Streamlit display state
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Persist user message to DB
    persist_message_to_db(session_id, "user", prompt)

    try:
        # Initiate chat - AutoGen handles the conversation flow internally
        # We clear history=False to maintain context within this specific turn/call
        # The agent's internal history (if configured) handles longer context.
        user.initiate_chat(
            agent,
            message=prompt,
            clear_history=False, # Keep history within this call
            request_reply=True, # Ensure we get a reply
        )

        # The response should be the last message in the agent's history
        raw_assistant_response = agent.last_message()["content"]

        # --- Parse the assistant response ---
        thinking_match = re.search(r"<think>(.*?)</think>", raw_assistant_response, re.DOTALL)
        thinking_process = thinking_match.group(1).strip() if thinking_match else None

        # The final answer is the part outside the <think> tags
        final_answer = re.sub(r"<think>.*?</think>", "", raw_assistant_response, flags=re.DOTALL).strip()

        # If there's no final answer after removing thinking, use the raw response
        if not final_answer and not thinking_process:
             final_answer = raw_assistant_response.strip()
        elif not final_answer and thinking_process:
             # If only thinking is present, maybe use that as the answer or indicate no answer
             final_answer = "Thinking process completed, but no final answer was generated." # Or handle as needed
        # --- End Parsing ---


        # Add the parsed response (including thinking) to Streamlit display state
        # We store both for display purposes, but only persist the final answer
        st.session_state.messages.append({
            "role": "assistant",
            "content": raw_assistant_response, # Store raw for parsing during display
            "thinking": thinking_process,
            "final_answer": final_answer
        })

        # Display the message immediately (will be re-rendered by rerun)
        # The actual display logic is in the main loop now

        # Persist ONLY the final answer to DB
        persist_message_to_db(session_id, "assistant", final_answer)

    except Exception as e:
        # --- Enhanced Error Logging ---
        import traceback
        error_details = traceback.format_exc()
        print("--- ERROR during handle_conversations ---") # ADDED PRINT
        print(error_details) # ADDED PRINT
        st.error(f"An error occurred during conversation: {e}")
        # --- End Enhanced Error Logging ---

        # Optionally persist an error message or handle differently
        error_message = "Sorry, I encountered an error processing your request."
        st.session_state.messages.append({"role": "assistant", "content": error_message})
        with st.chat_message("assistant"):
            st.markdown(error_message)
        persist_message_to_db(session_id, "assistant", f"Error: {e}")


def flush_database():
    """Truncates all data from the messages, sessions, and users tables."""
    print("--- Flushing database tables ---")
    success, conn, cursor = initialize_postgresql_client()
    if not success:
        st.error("Failed to connect to database for flushing.")
        return

    try:
        # Truncate tables all in one to prevent tables dependency
        cursor.execute("TRUNCATE TABLE messages, sessions, users RESTART IDENTITY;")
        print("--- Database tables flushed successfully ---")
        st.sidebar.success("Database flushed successfully!")
    except Exception as e:
        print(f"--- Error flushing database: {e} ---")
        st.error(f"An error occurred while flushing the database: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main():
    """Main application entry point."""
    print("--- main() function started ---") # ADDED PRINT

    # Set page configuration
    st.set_page_config(
        page_title="PostgreSQL Memory Agent",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # --- Database Setup ---
    # Check and setup DB first, but don't stop immediately
    db_ready = check_and_setup_db()

    # Add flush option in sidebar if DB is ready
    with st.sidebar:
        if db_ready:
            st.markdown("---") # Separator
            st.warning("Danger Zone: Flush Database")
            flush_confirm = st.checkbox("I understand that this will delete all chat history and user data.")
            if flush_confirm:
                if st.button("Flush Database"):
                    flush_database()
                    st.session_state.messages = [] # Clear Streamlit state messages too
                    st.session_state.chat_initialized = False # Reset chat state
                    st.rerun() # Rerun to show flushed state

    if not db_ready:
        st.error("Database is not ready. Please check terminal for setup details.")
        st.stop() # Stop execution if database is not ready after showing flush option

    # --- End Database Setup ---

    # Create a layout with columns for title and clear button
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("🧠 PostgreSQL Memory Agent")
        powered_by_html = """<div style='display: flex; align-items: center; gap: 10px; margin-top: 5px;'><span style='font-size: 20px; color: #666;'>Powered by</span><img src="https://docs.ag2.ai/latest/assets/img/logo.svg" width="80"></div>"""
        st.markdown(powered_by_html, unsafe_allow_html=True)

    # Clear chat history button
    with col2:
        if st.button("Clear ↺"):
            st.session_state.messages = []
            st.rerun()

    # Sidebar for user information and controls
    with st.sidebar:
        st.info(
            "Please enter your name to begin chatting 💬"
        )

        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")

        if st.button("Initialize Session") and first_name and last_name:
            print("--- Initialize Session button clicked ---") # ADDED PRINT
            initialize_session(first_name, last_name)

    print("--- Past sidebar section in main() ---") # ADDED PRINT
    # Main chat interface
    if st.session_state.get("chat_initialized", False):
        # Create agents only if initialized
        agent, user = create_agents()

        if agent and user: # Check if agents were created successfully
            # Display existing messages from session state
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    if message["role"] == "user":
                        st.markdown(message["content"])
                    elif message["role"] == "assistant":
                        # Parse and display assistant message with thinking section
                        raw_content = message.get("content", "")
                        thinking_process = message.get("thinking") # Use stored thinking if available
                        final_answer = message.get("final_answer") # Use stored final_answer if available

                        # If not stored (e.g., old messages or direct DB load), parse now
                        if thinking_process is None or final_answer is None:
                            thinking_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
                            thinking_process = thinking_match.group(1).strip() if thinking_match else None
                            final_answer = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
                            if not final_answer and not thinking_process:
                                final_answer = raw_content.strip()
                            elif not final_answer and thinking_process:
                                final_answer = "Thinking process completed, but no final answer was generated."

                        if thinking_process:
                            with st.expander("Thinking Process"):
                                st.markdown(thinking_process)

                        st.markdown(final_answer)

            # Handle new user input
            prompt_input = st.chat_input("How can I assist you?")
            if prompt_input:
                handle_conversations(agent, user, prompt_input)
                # Rerun to display the new messages immediately after processing
                st.rerun()
        else:
            # This case should ideally not be reached if initialization logic is correct
            st.warning("Agents could not be created. Please ensure session is initialized.")
    else:
        # Show a message if the session is not initialized
        st.info("Please enter your name and initialize the session using the sidebar.")
        # Removed chat input handling here to prevent errors when agent/user are None

# Ensure main is called if script is run directly
if __name__ == "__main__":
    print("--- Script execution started (__name__ == '__main__') ---") # ADDED PRINT
    main()
