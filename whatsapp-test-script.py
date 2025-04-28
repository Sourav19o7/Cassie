#!/usr/bin/env python3
"""
WhatsApp Integration Test Script for Empathic Problem Solver CLI
This script tests the WhatsApp integration module and helps diagnose issues.
"""

import os
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Add the current directory to the path to import the module
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Initialize console
console = Console()

console.print(Panel(
    "WhatsApp Integration Test Script for Empathic Problem Solver CLI",
    title="Test Script",
    border_style="green"
))

# Try to import the whatsapp_integration module
try:
    import whatsapp_integration
    console.print("[green]Successfully imported whatsapp_integration module.[/green]")
except ImportError as e:
    console.print(f"[red]Error importing whatsapp_integration module: {e}[/red]")
    console.print("[yellow]Make sure the module is in the current directory or in the Python path.[/yellow]")
    sys.exit(1)

# Check if Selenium is available
if whatsapp_integration.SELENIUM_AVAILABLE:
    console.print("[green]Selenium is available. Browser automation can be used.[/green]")
else:
    console.print("[yellow]Selenium is not available. WhatsApp export files will be used instead.[/yellow]")
    console.print("Run 'pip install selenium webdriver-manager' to enable browser automation.")

# Initialize WhatsApp integration
config = whatsapp_integration.init_whatsapp_integration()
console.print(f"[cyan]WhatsApp integration initialized with config:[/cyan]")
console.print(f"- Enabled: {config.get('whatsapp_web_enabled', False)}")
console.print(f"- Browser: {config.get('browser_type', 'chrome')}")
console.print(f"- Monitored groups: {config.get('monitored_groups', [])}")
console.print(f"- Use export files: {config.get('use_export', False)}")

# Test options
console.print("\n[bold]Available Tests:[/bold]")
console.print("1. Test WhatsApp connection")
console.print("2. Test scan with browser automation")
console.print("3. Test scan with export files")
console.print("4. Test WebDriver initialization")
console.print("5. Diagnose selectors")
console.print("6. Enable debug mode and scan")
console.print("7. Create test tasks with fallback method")
console.print("8. Exit")

while True:
    choice = input("\nSelect a test (1-8): ")
    
    if choice == "1":
        console.print("[cyan]Testing WhatsApp Web connection...[/cyan]")
        result = whatsapp_integration.test_whatsapp_connection()
        if result:
            console.print("[green]Connection test successful![/green]")
        else:
            console.print("[red]Connection test failed. See above for details.[/red]")
    
    elif choice == "2":
        console.print("[cyan]Testing WhatsApp scan with browser automation...[/cyan]")
        if not whatsapp_integration.SELENIUM_AVAILABLE:
            console.print("[yellow]Selenium is not available. Skipping this test.[/yellow]")
            continue
            
        # Temporarily ensure browser automation is used
        original_use_export = config.get("use_export", False)
        config["use_export"] = False
        whatsapp_integration.save_whatsapp_config(config)
        
        result = whatsapp_integration.scan_whatsapp_messages()
        
        # Restore original setting
        config["use_export"] = original_use_export
        whatsapp_integration.save_whatsapp_config(config)
        
        if result:
            console.print("[green]Scan with browser automation successful![/green]")
        else:
            console.print("[yellow]Scan with browser automation completed with warnings. See above for details.[/yellow]")
    
    elif choice == "3":
        console.print("[cyan]Testing WhatsApp scan with export files...[/cyan]")
        export_path = config.get("export_path", str(Path.home() / "Downloads"))
        console.print(f"Looking for WhatsApp export files in: {export_path}")
        
        # Temporarily force use of export files
        original_use_export = config.get("use_export", False)
        config["use_export"] = True
        whatsapp_integration.save_whatsapp_config(config)
        
        result = whatsapp_integration.scan_whatsapp_messages()
        
        # Restore original setting
        config["use_export"] = original_use_export
        whatsapp_integration.save_whatsapp_config(config)
        
        if result:
            console.print("[green]Scan with export files successful![/green]")
        else:
            console.print("[yellow]Scan with export files completed with warnings. See above for details.[/yellow]")
    
    elif choice == "4":
        console.print("[cyan]Testing WebDriver initialization...[/cyan]")
        if not whatsapp_integration.SELENIUM_AVAILABLE:
            console.print("[yellow]Selenium is not available. Skipping this test.[/yellow]")
            continue
            
        browser_type = config.get("browser_type", "chrome")
        console.print(f"Initializing {browser_type} WebDriver...")
        
        driver = whatsapp_integration.initialize_webdriver(
            browser_type, 
            False,  # Non-headless for testing
            config
        )
        
        if driver:
            console.print("[green]WebDriver initialized successfully![/green]")
            console.print("Loading https://web.whatsapp.com/ to test browser...")
            try:
                driver.get("https://web.whatsapp.com/")
                console.print("[green]Successfully loaded WhatsApp Web.[/green]")
                console.print("Waiting 5 seconds before closing browser...")
                time.sleep(5)
            except Exception as e:
                console.print(f"[red]Error loading WhatsApp Web: {e}[/red]")
            finally:
                driver.quit()
                console.print("[green]WebDriver closed.[/green]")
        else:
            console.print("[red]Failed to initialize WebDriver.[/red]")
    
    elif choice == "5":
        console.print("[cyan]Diagnosing WhatsApp Web selectors...[/cyan]")
        if not whatsapp_integration.SELENIUM_AVAILABLE:
            console.print("[yellow]Selenium is not available. Skipping this test.[/yellow]")
            continue
            
        browser_type = config.get("browser_type", "chrome")
        driver = whatsapp_integration.initialize_webdriver(
            browser_type, 
            False,  # Non-headless for testing
            config
        )
        
        if not driver:
            console.print("[red]Failed to initialize WebDriver.[/red]")
            continue
        
        try:
            driver.get("https://web.whatsapp.com/")
            console.print("[green]Successfully loaded WhatsApp Web.[/green]")
            console.print("[cyan]Waiting for 30 seconds to allow for login...[/cyan]")
            
            # Wait for login
            chat_list_found = whatsapp_integration.wait_for_chat_list(driver, 30)
            
            if not chat_list_found:
                console.print("[yellow]Chat list not found. Please log in within 30 seconds.[/yellow]")
                chat_list_found = whatsapp_integration.wait_for_chat_list(driver, 30)
                
                if not chat_list_found:
                    console.print("[red]Still couldn't find chat list. Aborting selector diagnosis.[/red]")
                    driver.quit()
                    continue
            
            console.print("[green]Chat list found. Testing other selectors...[/green]")
            
            # Test search box
            search_found = False
            for selector in whatsapp_integration.WHATSAPP_SELECTORS['chat_search']:
                try:
                    search_element = driver.find_element(whatsapp_integration.By.XPATH, selector)
                    if search_element.is_displayed():
                        console.print(f"[green]Found search box with selector: {selector}[/green]")
                        search_found = True
                        break
                except Exception:
                    pass
            
            if not search_found:
                console.print("[red]Could not find search box with any selector.[/red]")
            
            # Test message container
            message_container_found = False
            for selector in whatsapp_integration.WHATSAPP_SELECTORS['message_container']:
                try:
                    container_element = driver.find_element(whatsapp_integration.By.XPATH, selector)
                    console.print(f"[green]Found message container with selector: {selector}[/green]")
                    message_container_found = True
                    break
                except Exception:
                    pass
            
            if not message_container_found:
                console.print("[yellow]Could not find message container. You may need to open a chat first.[/yellow]")
                
            console.print("[green]Selector diagnosis completed.[/green]")
            
        except Exception as e:
            console.print(f"[red]Error during selector diagnosis: {e}[/red]")
        finally:
            driver.quit()
            console.print("[green]WebDriver closed.[/green]")
    
    elif choice == "6":
        console.print("[cyan]Enabling debug mode and scanning...[/cyan]")
        
        # Enable verbose output
        debug_mode = True
        
        # Try to scan with debug logging
        if whatsapp_integration.SELENIUM_AVAILABLE:
            browser_type = config.get("browser_type", "chrome")
            driver = whatsapp_integration.initialize_webdriver(
                browser_type, 
                False,  # Non-headless for debugging
                config
            )
            
            if not driver:
                console.print("[red]Failed to initialize WebDriver.[/red]")
                continue
            
            try:
                driver.get("https://web.whatsapp.com/")
                console.print("[green]Successfully loaded WhatsApp Web.[/green]")
                
                # Wait for login
                chat_list_found = whatsapp_integration.wait_for_chat_list(driver, 30)
                
                if not chat_list_found:
                    console.print("[yellow]Chat list not found. Please log in within 30 seconds.[/yellow]")
                    chat_list_found = whatsapp_integration.wait_for_chat_list(driver, 30)
                    
                    if not chat_list_found:
                        console.print("[red]Still couldn't find chat list. Aborting debug scan.[/red]")
                        driver.quit()
                        continue
                
                console.print("[green]Chat list found. Attempting to find and select a group...[/green]")
                
                # Get a group to test with
                monitored_groups = config.get("monitored_groups", [])
                if not monitored_groups:
                    console.print("[yellow]No monitored groups configured. Add at least one group first.[/yellow]")
                    driver.quit()
                    continue
                
                test_group = monitored_groups[0]
                console.print(f"[cyan]Testing with group: {test_group}[/cyan]")
                
                # Try to find and click on the group
                search_found = whatsapp_integration.find_and_interact_with_search_box(driver, test_group)
                if not search_found:
                    console.print("[red]Could not find or interact with search box.[/red]")
                    driver.quit()
                    continue
                
                console.print("[green]Search interaction successful. Trying to click on group...[/green]")
                
                group_found = whatsapp_integration.click_on_contact_or_group(driver, test_group)
                if not group_found:
                    console.print("[red]Could not find or click on the group.[/red]")
                    driver.quit()
                    continue
                
                console.print("[green]Successfully clicked on group. Extracting messages...[/green]")
                
                messages = whatsapp_integration.extract_messages(driver, 10)
                console.print(f"[cyan]Found {len(messages)} messages.[/cyan]")
                
                if not messages:
                    console.print("[red]No messages found in the group.[/red]")
                    driver.quit()
                    continue
                
                console.print("[green]Extracting message info from the first message...[/green]")
                
                message_info = whatsapp_integration.extract_message_info(messages[0])
                console.print(f"Sender: {message_info['sender']}")
                console.print(f"Text: {message_info['text'][:50]}..." if len(message_info['text']) > 50 else message_info['text'])
                
                console.print("[green]Debug scan completed successfully.[/green]")
                
            except Exception as e:
                console.print(f"[red]Error during debug scan: {e}[/red]")
            finally:
                driver.quit()
                console.print("[green]WebDriver closed.[/green]")
        else:
            console.print("[yellow]Selenium is not available. Using fallback debug mode.[/yellow]")
            result = whatsapp_integration.use_fallback_method()
            if result:
                console.print("[green]Fallback method completed successfully.[/green]")
            else:
                console.print("[red]Fallback method failed.[/red]")
    
    elif choice == "7":
        console.print("[cyan]Creating test tasks with fallback method...[/cyan]")
        result = whatsapp_integration.use_fallback_method()
        if result:
            console.print("[green]Test tasks created successfully![/green]")
        else:
            console.print("[red]Failed to create test tasks.[/red]")
    
    elif choice == "8":
        console.print("[cyan]Exiting test script...[/cyan]")
        break
    
    else:
        console.print("[yellow]Invalid choice. Please enter a number between 1 and 8.[/yellow]")

console.print(Panel(
    "WhatsApp Integration Test Script Complete",
    border_style="green"
))