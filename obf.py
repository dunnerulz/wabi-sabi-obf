import re
import random
import string
import math

class WabiSabiObfuscator:
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
        """
        Encrypts a string for the Ea() function.
        Matches the logic: 
        byte(char) XOR byte(key[(i + math_offset) % len(key)])
        The math offset in Lua is (kd-2053812/22084)%#da
        2053812 / 22084 approx 93. So (kd - 93) % key_len.
        To keep Python sync simple, we will simulate the result the Lua code expects.
        """
        encrypted_chars = []
        key_len = len(key)
        
        # The Lua math noise: (kd-2053812/22084)%#da
        # We can just pick a static integer for the Python side that represents the result of that division
        # 2053812 / 22084 = 93.0
        OFFSET_VAL = 93 
        
        for i, char in enumerate(text):
            kd = i + 1 # Lua uses 1-based indexing for the loop
            
            # Calculate the index of the key character used in Lua
            # Lua: (kd - 93) % #da + 1  (because lua arrays are 1-based)
            # We map this to 0-based index for Python string access:
            # key_index = ((kd - 93) % key_len) 
            # Note: Python % handles negative numbers differently than Lua for some cases, 
            # but for simple encryption rotation it's fine if we are consistent.
            # To be safe and match Lua's behavior exactly:
            lua_mod_index = (kd - OFFSET_VAL) % key_len
            
            # Since Lua 1-based index `+1` is usually done after mod, the char at `lua_mod_index` 
            # in Python (0-based) corresponds to the key char used.
            key_char_code = ord(key[int(lua_mod_index)])
            
            char_code = ord(char)
            enc_code = char_code ^ key_char_code
            encrypted_chars.append(f"\\{enc_code}")
            
        return "".join(encrypted_chars)

    def _mangle_number(self, num_str):
        """
        Constant Folding / Number Mangling
        """
        try:
            val = float(num_str)
            if val == 0: return "(0)"
            if val == 1: return "(1)"
            
            is_integer = val.is_integer()
            op_type = random.choice([0, 1, 3]) 
            
            if op_type == 0: # Addition
                part_a = random.randint(1000, 100000)
                part_b = val - part_a
                return f"({part_a}+{part_b})"
                
            elif op_type == 1: # Subtraction
                part_b = random.randint(1000, 100000)
                part_a = val + part_b
                return f"({part_a}-{part_b})"
                
            elif op_type == 3: # Division
                if is_integer:
                    factor = random.randint(2, 50)
                    numerator = int(val * factor)
                    return f"({numerator}/{factor})"
                else:
                    factor = random.randint(100, 100000)
                    numerator = val * factor
                    return f"({numerator}/{factor})"
            
            return num_str
        except:
            return num_str

    def _mangle_string(self, text):
        """Wraps string in Ea('encrypted', 'key')"""
        # Generate random key
        key = self._generate_random_string(random.randint(4, 8))
        encrypted = self._xor_encrypt(text, key)
        
        # Mangle the key string itself so it's not plain text in the source?
        # For now, we leave the key as a plain string literal to avoid infinite recursion
        # but in a real Wabi Sabi environment, the key itself might be obfuscated further or generated.
        # We will just return the Ea call.
        
        return f"{self.var_Ea}('{encrypted}','{key}')"

    def _mangle_globals(self, lua_code):
        """
        Replaces global function calls with Ma[Ea('print')]...
        Includes a check to avoid mangling 'local game =' declarations or table properties.
        """
        # List of common globals to mangle (Standard Lua + Roblox/Matcha Specifics)
        targets = [
            "print", "warn", "error", "game", "workspace", "math", "table", "string", 
            "task", "wait", "spawn", "getfenv", "setfenv", "pcall", "xpcall", 
            "pairs", "ipairs", "next", "type", "tostring", "tonumber", "select", 
            "unpack", "require", "Drawing", "Vector2", "Vector3", "CFrame", 
            "Color3", "UDim2", "Instance", "Enum", "RaycastParams", "Random", 
            "utf8", "os", "coroutine", "debug", "tick", "time", "delay", "defer",
            "getgenv", "getrenv", "identifyexecutor", "setclipboard", "readfile", 
            "writefile", "isfile", "delfile", "listfiles", "makefolder", "delfolder",
            "iskeypressed", "mouse1click", "ismouse1pressed", "mouse2click", "ismouse2pressed"
        ]
        
        # Sort targets by length descending to prevent substring issues (e.g. replacing 'os' inside 'position')
        targets.sort(key=len, reverse=True)

        for target in targets:
            # Regex Explanation:
            # (?<!\.)       : Negative lookbehind. Ensures the target is NOT preceded by a dot (e.g. avoid mangling myTable.print)
            # (\blocal\s+)? : Optional Group 1. Matches 'local ' followed by whitespace. 
            #                 Used to detect variable declarations.
            # \bTARGET\b    : Matches the target word with word boundaries (e.g. matches 'game' but not 'gameplay')
            
            pattern = r'(?<!\.)(\blocal\s+)?\b(' + re.escape(target) + r')\b'
            
            def replace_match(match):
                prefix = match.group(1) # 'local ' or None
                word = match.group(2)   # The target global name
                
                # If preceded by 'local ', do NOT mangle the name (e.g., 'local game')
                if prefix:
                    return f"{prefix}{word}"
                
                # Otherwise, mangle it (e.g., '= game' becomes '= Ma[Ea("game", key)]')
                return f"{self.var_Ma}[{self._mangle_string(word)}]"
            
            lua_code = re.sub(pattern, replace_match, lua_code)
            
        return lua_code

    def _generate_header(self):
        """Generates the Wabi Sabi boilerplate (Ma, Ea, Ta)"""
        # Defines the Ea function with the specific math noise mentioned in prompt:
        # (kd-2053812/22084)%#da
        # 2053812/22084 evaluates to ~93.
        
        return f"""-- Generated by Wabi Sabi Obfuscator
local {self.var_Ma}=(getfenv())
local {self.var_string_char},{self.var_string_byte},{self.var_bit_xor}=(string.char),(string.byte),(bit32 and bit32.bxor or function(a,b) local p,c=1,0 while a>0 and b>0 do local ra,rb=a%2,b%2 if ra~=rb then c=c+p end a,b,p=(a-ra)/2,(b-rb)/2,p*2 end if a<b then a=b end while a>0 do local ra=a%2 if ra>0 then c=c+p end a,p=(a-ra)/2,p*2 end return c end)
local {self.var_Ea}=function(ib,da)
    local Vb=''
    for kd=1,#ib do
        local key_char = {self.var_string_byte}(da, (kd-2053812/22084)%#da + 1)
        local str_char = {self.var_string_byte}(ib, kd)
        Vb=Vb..{self.var_string_char}({self.var_bit_xor}(str_char, key_char))
    end
    return Vb
end
"""

    def obfuscate(self, lua_source):
        """
        Logic:
        1. Mangle Numbers (Constant Folding)
        2. Mangle Strings (Polyadic XOR)
        3. Environment Virtualization (Globals -> Ma[Ea])
        """
        
        # 1. Mangle Numbers
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        def replace_number(match):
            return self._mangle_number(match.group(0))
        
        protected_code = re.sub(number_pattern, replace_number, lua_source)
        
        # 2. Mangle Strings
        # Matches either "..." or '...'
        string_pattern = r'("([^"]*)"|\'([^\']*)\')'
        
        def replace_string(match):
            if match.group(2) is not None:
                content = match.group(2)
            else:
                content = match.group(3)
            return self._mangle_string(content)

        protected_code = re.sub(string_pattern, replace_string, protected_code)

        # 3. Mangle Globals (Environment Virtualization)
        # We do this LAST so that the strings generated here (keys for Ea) don't get re-mangled.
        protected_code = self._mangle_globals(protected_code)

        # 4. Prepend Header
        final_code = self._generate_header() + "\n" + protected_code
        
        return final_code

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

    obfuscator = WabiSabiObfuscator()
    protected = obfuscator.obfuscate(input_code)
    
    with open("output.lua", "w") as f:
        f.write(protected)
    
    print("Obfuscation Complete! Saved to output.lua")
