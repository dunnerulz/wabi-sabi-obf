import re
import random
import string
import math

class MoonveilObfuscator:
    def __init__(self):
        self.var_Ma = "Ma"  # The global environment proxy
        self.var_Ea = "Ea"  # The string decryptor
        self.var_Ta = "Ta"  # The table holding code blocks
        self.var_string_char = "Q"
        self.var_string_byte = "Ca"
        self.var_bit_xor = "ed"
        
    def _generate_random_string(self, length=6):
        return ''.join(random.choices(string.ascii_letters, k=length))

    def _xor_encrypt(self, text, key):
        """Encrypts a string for the Ea() function"""
        encrypted_chars = []
        for i, char in enumerate(text):
            char_code = ord(char)
            # Simple shifting logic to match the Lua decryptor
            # (In a full version, this would be a complex bitwise op)
            enc_code = char_code ^ (ord(key[i % len(key)]) % 255)
            encrypted_chars.append(f"\\{enc_code}")
        return "".join(encrypted_chars)

    def _mangle_number(self, num_str):
        """
        Constant Folding / Number Mangling
        Turns '5' into '10452-10447'
        Turns '0.5' into '39600/79200'
        """
        try:
            val = float(num_str)
            
            # Preserve 0 and 1 slightly more cleanly to avoid heavy nesting on trivial checks
            if val == 0: return "(0)"
            if val == 1: return "(1)"
            
            # Determine if we should use integer math or float math
            is_integer = val.is_integer()
            
            # Strategy: Pick a random operation type
            # 0: Addition (target = part_a + part_b) -> target = part_a + (target - part_a)
            # 1: Subtraction (target = part_a - part_b) -> target = (target + part_b) - part_b
            # 2: Multiplication (target = part_a * part_b) -> only if factors found (harder for arbitrary floats)
            # 3: Division (target = part_a / part_b) -> target = (target * factor) / factor
            
            op_type = random.choice([0, 1, 3]) # Skip mult for now as it requires factoring
            
            if op_type == 0: # Addition: val = a + b
                part_a = random.randint(1000, 100000)
                part_b = val - part_a
                # Result: (part_a + part_b)
                return f"({part_a}+{part_b})"
                
            elif op_type == 1: # Subtraction: val = a - b
                part_b = random.randint(1000, 100000)
                part_a = val + part_b
                # Result: (part_a - part_b)
                return f"({part_a}-{part_b})"
                
            elif op_type == 3: # Division: val = a / b
                if is_integer:
                    # For integers, pick a random divisor (factor)
                    factor = random.randint(2, 50)
                    numerator = int(val * factor)
                    # Result: (numerator / factor)
                    return f"({numerator}/{factor})"
                else:
                    # For floats (e.g., 0.5), pick a large factor to make it look like a fraction
                    # 0.5 -> 500 / 1000
                    factor = random.randint(100, 100000)
                    numerator = val * factor
                    # Result: (numerator / factor)
                    return f"({numerator}/{factor})"
            
            return num_str
            
        except:
            return num_str

    def _mangle_string(self, text):
        """Wraps string in Ea('encrypted', 'key')"""
        key = self._generate_random_string(4)
        encrypted = self._xor_encrypt(text, key)
        # Using the Moonveil signature call: Ea('enc', 'key')
        return f"{self.var_Ea}('{encrypted}','{key}')"

    def _mangle_globals(self, lua_code):
        """
        Replaces global function calls with Ma[Ea('print')]...
        Now includes a check to avoid mangling 'local game =' declarations.
        """
        # List of common globals to mangle
        targets = ["print", "warn", "game", "workspace", "math", "table", "string", "task", "wait", "spawn"]
        
        # Replace 'game' with Ma[Ea('game', key)]
        for target in targets:
            # Pattern captures optional 'local ' prefix
            # Group 1: 'local ' (or None)
            # Group 2: The target word
            pattern = r'(\blocal\s+)?\b(' + re.escape(target) + r')\b'
            
            def replace_match(match):
                prefix = match.group(1)
                word = match.group(2)
                
                # If preceded by 'local ', do NOT mangle the name (e.g., 'local game')
                if prefix:
                    return f"{prefix}{word}"
                
                # Otherwise, mangle it (e.g., '= game')
                return f"{self.var_Ma}[{self._mangle_string(word)}]"
            
            lua_code = re.sub(pattern, replace_match, lua_code)
            
        return lua_code

    def _generate_header(self):
        """Generates the Moonveil boilerplate (Ma, Ea, Ta)"""
        # Fixed the #{self.var_string_byte}(da) bug to #da
        return f"""-- Generated by Moonveil Base Implementation
local {self.var_Ma}=(getfenv())
local {self.var_string_char},{self.var_string_byte},{self.var_bit_xor}=(string.char),(string.byte),(bit32 and bit32.bxor or function(a,b) local p,c=1,0 while a>0 and b>0 do local ra,rb=a%2,b%2 if ra~=rb then c=c+p end a,b,p=(a-ra)/2,(b-rb)/2,p*2 end if a<b then a=b end while a>0 do local ra=a%2 if ra>0 then c=c+p end a,p=(a-ra)/2,p*2 end return c end)
local {self.var_Ea}=function(ib,da)
    local Vb=''
    for kd=1,#ib do
        local key_char = {self.var_string_byte}(da, (kd-1)%#da + 1)
        local str_char = {self.var_string_byte}(ib, kd)
        Vb=Vb..{self.var_string_char}({self.var_bit_xor}(str_char, key_char))
    end
    return Vb
end
local {self.var_Ta}={{}}
"""

    def obfuscate(self, lua_source):
        """
        New simplified obfuscation logic:
        1. No CFF (Control Flow Flattening)
        2. No Global Mangling
        3. No String Mangling
        4. ONLY Number Mangling (with float support)
        """
        
        # We process the whole source string directly to avoid breaking multiline structures by line-splitting
        
        # Regex to match numbers, including floats (e.g., 100, 3.14, 0.5)
        # Explaining the pattern:
        # \b       : Word boundary (start of number)
        # \d+      : One or more digits
        # (?:      : Non-capturing group for decimals
        #   \.     : Literal dot
        #   \d+    : One or more digits
        # )?       : Optional decimal part
        # \b       : Word boundary (end of number)
        # Note: This might miss .5 starting with dot, but is safer for now.
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        
        def replace_number(match):
            original = match.group(0)
            return self._mangle_number(original)
            
        # Apply number mangling
        protected_code = re.sub(number_pattern, replace_number, lua_source)
        
        # For this specific "Number Mangler Only" request, we don't need the Moonveil header 
        # (Ma, Ea) because we aren't using them in the code body.
        # Just return the code with mangled numbers.
        
        return "-- Moonveil: Number Mangler Mode\n" + protected_code

# --- Usage ---
if __name__ == "__main__":
    # Example Input (Matcha compatible)
    input_code = """
    print("Initializing Matcha Script...")
    local LocalPlayer = game:GetService("Players").LocalPlayer
    local RunService = game:GetService("RunService")
    
    local x = 100
    local y = 200.5
    
    print("Starting Loop")
    while true do
        print("Looping...")
        task.wait(1)
    end
    """
    
    # Read from file if exists, else use example
    try:
        with open("input.lua", "r") as f:
            input_code = f.read()
    except:
        pass

    obfuscator = MoonveilObfuscator()
    protected = obfuscator.obfuscate(input_code)
    
    with open("output.lua", "w") as f:
        f.write(protected)
    
    print("Obfuscation Complete! Saved to output.lua")
