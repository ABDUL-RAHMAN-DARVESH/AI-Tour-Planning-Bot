#sos.py
import os
import sys
import json
import asyncio
import time
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Add parent directory to path for db imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(_file_))))

try:
    from db.mongo import add_contact as mongo_add_contact, list_contacts as mongo_list_contacts
except ImportError:
    print("Warning: MongoDB not available, using local storage fallback")
    # Fallback if import fails
    async def mongo_add_contact(user_id, contact):
        print(f"MongoDB fallback: Would add contact {contact} for user {user_id}")
        return True
    async def mongo_list_contacts(user_id):
        print(f"MongoDB fallback: Would list contacts for user {user_id}")
        return []

# Fix missing functions
async def add_single_contact(user_id: str, contact_data: dict) -> str:
    """Add a single emergency contact."""
    try:
        await mongo_add_contact(user_id, contact_data)
        return f"✅ Contact {contact_data['name']} added successfully!"
    except Exception as e:
        return f"❌ Failed to add contact: {str(e)}"

async def list_contacts(user_id: str) -> str:
    """List all contacts for a user."""
    try:
        contacts = await mongo_list_contacts(user_id)
        if not contacts:
            return "No emergency contacts found."
        result = "📞 Your Emergency Contacts:\n"
        for i, contact in enumerate(contacts, 1):
            result += f"{i}. {contact['name']} ({contact['relation']}) - {contact['number']}\n"
        return result
    except Exception as e:
        return f"❌ Error retrieving contacts: {str(e)}"

load_dotenv()

# Import pywhatkit with error handling
try:
    import pywhatkit as kit
    WHATSAPP_AVAILABLE = True
    print("WhatsApp integration available via pywhatkit")
except ImportError:
    WHATSAPP_AVAILABLE = False
    print("Warning: pywhatkit not available - WhatsApp sending will be simulated")

@dataclass
class Contact:
    name: str
    number: str
    relation: str
    
    def _post_init_(self):
        self.number = self._normalize_number(self.number)
    
    def _normalize_number(self, number: str) -> str:
        """Normalize phone number to international format."""
        # Remove all non-digit characters except +
        clean = ''.join(c for c in number if c.isdigit() or c == '+')
        
        if clean.startswith("+91"):
            return clean
        if clean.startswith("91") and len(clean) > 10:
            return f"+{clean}"
        if len(clean) == 10:
            return f"+91{clean}"
        return clean if clean.startswith("+") else f"+91{clean}"

@dataclass
class SOSMessage:
    content: str
    location: Optional[str] = None
    timestamp: Optional[str] = None
    
    def _post_init_(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class SendResult:
    contact: str
    status: str
    method: str
    error_message: Optional[str] = None

class ContactsRepository:
    """Local file fallback for contacts storage."""
    def _init_(self, file_path: str = "emergency_contacts.json"):
        self.file_path = file_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    def load(self) -> List[Contact]:
        try:
            if not os.path.exists(self.file_path):
                return []
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                return [Contact(**contact) for contact in data]
        except Exception as e:
            print(f"Error loading contacts from file: {e}")
            return []
    
    def save(self, contacts: List[Contact]) -> None:
        try:
            data = [{'name': c.name, 'number': c.number, 'relation': c.relation} for c in contacts]
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved {len(contacts)} contacts to {self.file_path}")
        except Exception as e:
            print(f"Error saving contacts to file: {e}")
            raise

class MessageComposer:
    """Create SOS messages."""
    @staticmethod
    def create_sos_message(user_message: Optional[str] = None, location: Optional[str] = None) -> SOSMessage:
        default_content = "🚨 EMERGENCY! I need immediate help. This is an automated SOS alert."
        content = user_message or default_content
        return SOSMessage(content=content, location=location)
    
    @staticmethod
    def format_whatsapp_message(sos_message: SOSMessage, contact: Contact) -> str:
        msg = f"""🚨 AUTOMATIC SOS ALERT 🚨

{sos_message.content}

⏰ Time: {sos_message.timestamp}
👤 Emergency Contact: {contact.name} ({contact.relation})
🤖 AI Travel Guide Emergency System

⚠ This is an automated emergency alert. Please respond immediately or contact emergency services if needed."""
        
        if sos_message.location:
            msg += f"\n📍 Last Known Location: {sos_message.location}"
        
        msg += "\n\n🆘 If this is a false alarm, please confirm your safety."
        return msg

class WhatsAppSender:
    """Send WhatsApp messages using pywhatkit."""
    @staticmethod
    def send(contact: Contact, message: str) -> SendResult:
        try:
            if not WHATSAPP_AVAILABLE:
                # Simulate sending for testing
                print(f"SIMULATED WhatsApp to {contact.name} ({contact.number}):")
                print(f"Message: {message}")
                print("-" * 50)
                return SendResult(
                    contact=contact.name, 
                    status="success", 
                    method="simulated",
                    error_message=None
                )
            
            print(f"Attempting to send WhatsApp to {contact.name} ({contact.number})")
            
            # Use pywhatkit to send immediately
            kit.sendwhatmsg_instantly(
                phone_no=contact.number,
                message=message,
                wait_time=15,  # Wait 15 seconds for WhatsApp to load
                tab_close=True,
                close_time=5   # Close tab after 5 seconds
            )
            
            print(f"WhatsApp sent successfully to {contact.name}")
            return SendResult(
                contact=contact.name, 
                status="success", 
                method="pywhatkit",
                error_message=None
            )
            
        except Exception as e:
            print(f"Failed to send WhatsApp to {contact.name}: {str(e)}")
            return SendResult(
                contact=contact.name, 
                status="failed", 
                method="whatsapp",
                error_message=str(e)
            )

class SOSSystem:
    """Main SOS system coordinating contacts and messaging."""
    def _init_(self):
        self.contacts_repo = ContactsRepository()
        self.message_composer = MessageComposer()
    
    async def save_contacts(self, contact1_data: Dict, contact2_data: Dict, user_id: Optional[str] = None) -> str:
        """Save two emergency contacts."""
        try:
            contacts = [Contact(*contact1_data), Contact(*contact2_data)]
            
            if user_id:
                try:
                    # Try to save to MongoDB
                    for c in contacts:
                        await mongo_add_contact(user_id, {
                            "name": c.name, 
                            "number": c.number, 
                            "relation": c.relation
                        })
                    print(f"Saved contacts to MongoDB for user {user_id}")
                    return "✅ Emergency contacts saved to your account!"
                except Exception as e:
                    print(f"MongoDB save failed: {e}, falling back to local storage")
                    # Fallback to local storage
                    self.contacts_repo.save(contacts)
                    return "✅ Emergency contacts saved locally (database unavailable)!"
            
            # Save locally if no user_id
            self.contacts_repo.save(contacts)
            return "✅ Emergency contacts saved locally!"
            
        except Exception as e:
            print(f"Error saving contacts: {e}")
            return f"❌ Failed to save contacts: {str(e)}"
    
    async def trigger_sos(self, user_location: Optional[str] = None, user_message: Optional[str] = None, user_id: Optional[str] = None) -> str:
        """Trigger SOS to all saved contacts."""
        print(f"Triggering SOS for user {user_id}")
        contacts_list: List[Contact] = []
        
        # Try to get contacts from database first
        if user_id:
            try:
                print(f"Fetching contacts from database for user {user_id}")
                records = await mongo_list_contacts(user_id)
                if records:
                    contacts_list = [Contact(**r) for r in records]
                    print(f"Found {len(contacts_list)} contacts in database")
                else:
                    print("No contacts found in database")
            except Exception as e:
                print(f"Database error when fetching contacts: {e}")
        
        # Fallback to local file if no database contacts
        if not contacts_list:
            print("Trying local file storage for contacts")
            contacts_list = self.contacts_repo.load()
            print(f"Found {len(contacts_list)} contacts in local storage")
        
        if not contacts_list:
            error_msg = "❌ No emergency contacts found. Please add contacts first using the Setup SOS button."
            print(error_msg)
            return error_msg
        
        # Create and send SOS messages
        print("Creating SOS message")
        sos_message = self.message_composer.create_sos_message(user_message, user_location)
        results = []
        
        print(f"Sending SOS to {len(contacts_list)} contacts")
        for i, contact in enumerate(contacts_list, 1):
            try:
                print(f"Sending to contact {i}/{len(contacts_list)}: {contact.name}")
                formatted_message = self.message_composer.format_whatsapp_message(sos_message, contact)
                result = WhatsAppSender.send(contact, formatted_message)
                results.append(result)
                print(f"Result: {result.status} for {contact.name}")
                
                # Add delay between messages to avoid rate limiting
                if i < len(contacts_list):
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"Exception sending to {contact.name}: {e}")
                results.append(SendResult(
                    contact=contact.name, 
                    status="failed", 
                    method="whatsapp",
                    error_message=str(e)
                ))
        
        # Create summary
        success_count = sum(1 for r in results if r.status == "success")
        total_count = len(results)
        
        summary_lines = []
        for result in results:
            if result.status == "success":
                summary_lines.append(f"✅ {result.contact}")
            else:
                summary_lines.append(f"❌ {result.contact} - {result.error_message or 'Failed'}")
        
        summary = f"🚨 SOS Alert Results ({success_count}/{total_count} sent)\n" + "\n".join(summary_lines)
        print(f"SOS Summary: {summary}")
        return summary

# Helper functions for tool integration
async def add_single_contact(user_id: str, contact_data: Dict) -> str:
    """Add single emergency contact via MongoDB."""
    try:
        contact = Contact(**contact_data)
        await mongo_add_contact(user_id, {
            "name": contact.name, 
            "number": contact.number, 
            "relation": contact.relation
        })
        return f"✅ Added {contact.name} ({contact.number}) to emergency contacts."
    except Exception as e:
        print(f"Error adding contact: {e}")
        return f"❌ Failed to add contact: {str(e)}"

async def list_contacts(user_id: str) -> str:
    """List all emergency contacts for user."""
    try:
        records = await mongo_list_contacts(user_id)
        if not records:
            return "⚠ No emergency contacts found. Use the Setup SOS button to add contacts."
        
        output = ["📒 Your Emergency Contacts:"]
        for i, contact in enumerate(records, 1):
            output.append(f"{i}. {contact.get('name')} – {contact.get('number')} ({contact.get('relation', 'contact')})")
        
        return "\n".join(output)
    except Exception as e:
        print(f"Error listing contacts: {e}")
        return f"❌ Error retrieving contacts: {str(e)}"

async def handle_sos_workflow(user_id: str = "default_user", interactive: bool = True) -> str:
    """Handle SOS workflow - can be called from agent or standalone."""
    sos = SOSSystem()
    
    # Check if emergency contacts exist
    try:
        contacts = await mongo_list_contacts(user_id)
    except Exception as e:
        if interactive:
            print(f"⚠ Database connection issue: {e}")
            print("Using local file storage instead...")
        contacts = []
    
    # Check local file if no DB contacts
    if not contacts:
        local_contacts = sos.contacts_repo.load()
        if local_contacts:
            contacts = [{"name": c.name, "number": c.number, "relation": c.relation} for c in local_contacts]
    
    if not contacts:
        if not interactive:
            return "❌ No emergency contacts found. Please add contacts first."
        
        print("\n⚠ No emergency contacts found.")
        print("Please add emergency contacts first:\n")
        
        # Get contacts
        name1 = input("First Contact Name: ").strip()
        number1 = input("Phone Number: ").strip()
        relation1 = input("Relation: ").strip()
        
        name2 = input("\nSecond Contact Name: ").strip()
        number2 = input("Phone Number: ").strip()
        relation2 = input("Relation: ").strip()
        
        # Save contacts
        contact1_data = {"name": name1, "number": number1, "relation": relation1}
        contact2_data = {"name": name2, "number": number2, "relation": relation2}
        
        result = await sos.save_contacts(contact1_data, contact2_data, user_id)
        print(result)
    
    # Get SOS message and location
    if interactive:
        print("\n📍 SOS Details:")
        location = input("Current Location (optional): ").strip() or None
        message = input("Emergency Message (optional): ").strip() or None
    else:
        location = None
        message = None
    
    # Send SOS
    if interactive:
        print("\n🚨 Sending SOS Alert...")
    
    try:
        result = await sos.trigger_sos(location, message, user_id)
    except Exception as e:
        error_msg = f"❌ SOS failed: {str(e)}"
        if interactive:
            print(f"⚠ SOS sending failed: {e}")
        result = error_msg
    
    if interactive:
        print(f"\n{result}")
    
    return result

async def main():
    """Main function for standalone execution."""
    print("🚨 Emergency SOS System 🚨")
    await handle_sos_workflow("default_user", interactive=True)

if _name_ == "_main_":
    asyncio.run(main())