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
        """
        encrypted_chars = []
        key_len = len(key)
        
        # The Lua math noise: (kd-2053812/22084)%#da
        # 2053812 / 22084 approx 93. So (kd - 93) % key_len.
        OFFSET_VAL = 93 
        
        for i, char in enumerate(text):
            kd = i + 1 # Lua uses 1-based indexing
            lua_mod_index = (kd - OFFSET_VAL) % key_len
            key_char_code = ord(key[int(lua_mod_index)])
            char_code = ord(char)
            enc_code = char_code ^ key_char_code
            encrypted_chars.append(f"\\{enc_code}")
            
        return "".join(encrypted_chars)

    def _mangle_number(self, num_str):
        try:
            val = float(num_str)
            if val == 0: return "((10-10)*5)"
            
            # MoonVeil Strategy: Float Multiplication
            # Target: 100
            # Gen: 0.05 * 2000
            factor = random.randint(1000, 50000)
            multiplier = val / factor
            # Lua format needs high precision
            return f"({multiplier} * {factor})"
        except:
            return num_str

    def _mangle_boolean(self, val):
        """
        MoonVeil Logic Gate Booleans:
        Avoids raw 'true' and 'false' literals by using conditions that evaluate to them.
        
        For True:  not(not X) where X is a truthy value (non-zero number)
                   or comparison like (50 > 20)
        For False: not(X) where X is a truthy value
        
        This obfuscates boolean literals to make static analysis harder.
        
        NOTE: We use raw integers here instead of calling _mangle_number() because
        the number mangling step in the pipeline will handle these integers later.
        This avoids issues with scientific notation being generated prematurely
        and then incorrectly re-mangled by the pipeline's number pattern.
        """
        if val:
            # True case: not(not X) where X is truthy (a non-zero number)
            # This double negation always evaluates to true for truthy values
            # Alternative: simple comparison like (50 > 20)
            strategy = random.choice(['double_not', 'comparison'])
            if strategy == 'double_not':
                # Use a raw integer; it will be mangled by the pipeline later
                num = random.randint(1, 999)
                return "not(not {})".format(num)
            else:
                # Comparison that always evaluates to true
                a = random.randint(50, 500)
                b = random.randint(1, 49)
                return "({} > {})".format(a, b)
        else:
            # False case: not(X) where X is truthy
            # Single negation of a truthy value always evaluates to false
            # Use a raw integer; it will be mangled by the pipeline later
            num = random.randint(1, 999)
            return "not({})".format(num)

    def _mangle_booleans(self, lua_code):
        """
        MoonVeil Logic Gate Booleans - Code Processing:
        Finds all 'true' and 'false' literals in the code and replaces them
        with logic gate expressions that evaluate to the same boolean value.
        
        Uses word boundary matching to avoid replacing partial words like 'istrue' or 'falsehood'.
        Also avoids replacing booleans inside strings by using a tokenizer approach.
        """
        tokens = self._tokenize(lua_code)
        transformed_tokens = []
        
        for kind, val in tokens:
            # Only transform IDENT tokens that are exactly 'true' or 'false'
            # This avoids touching strings, comments, or partial matches
            if kind == 'IDENT' and val == 'true':
                # Replace 'true' with a logic gate expression
                mangled = self._mangle_boolean(True)
                # Wrap in parens for safety in complex expressions
                transformed_tokens.append(('OP', '('))
                # Re-tokenize the mangled expression and add it
                mangled_tokens = self._tokenize(mangled)
                transformed_tokens.extend(mangled_tokens)
                transformed_tokens.append(('OP', ')'))
            elif kind == 'IDENT' and val == 'false':
                # Replace 'false' with a logic gate expression
                mangled = self._mangle_boolean(False)
                # Wrap in parens for safety in complex expressions
                transformed_tokens.append(('OP', '('))
                mangled_tokens = self._tokenize(mangled)
                transformed_tokens.extend(mangled_tokens)
                transformed_tokens.append(('OP', ')'))
            else:
                transformed_tokens.append((kind, val))
        
        return self._reconstruct(transformed_tokens)

    def _mangle_string(self, text):
        """Wraps string in Ea('encrypted', 'key')"""
        key = self._generate_random_string(random.randint(4, 8))
        encrypted = self._xor_encrypt(text, key)
        return f"{self.var_Ea}('{encrypted}','{key}')"

    def _mangle_globals(self, lua_code):
        """
        Replaces global function calls with Ma[Ea('print')]...
        """
        targets = [
            "print", "warn", "error", "game", "workspace", "math", "table", "string", 
            "task", "wait", "spawn", "getfenv", "setfenv", "pcall", "xpcall", 
            "pairs", "ipairs", "next", "type", "tostring", "tonumber", "select", 
            "unpack", "require", "Drawing", "Vector2", "Vector3", "CFrame", 
            "Color3", "UDim2", "Instance", "Enum", "RaycastParams", "Random", 
            "utf8", "os", "coroutine", "debug", "tick", "time", "delay", "defer",
            "getgenv", "getrenv", "identifyexecutor", "setclipboard", "readfile", 
            "writefile", "isfile", "delfile", "listfiles", "makefolder", "delfolder",
            "iskeypressed", "mouse1click", "ismouse1pressed", "mouse2click", "ismouse2pressed",
            "getscripthash", "isrbxactive", "keyrelease", "keypress", "mouse1press",
            "mouse1release", "mouse2press", "mouse2release", "mousemoveabs", "mousemoverel",
            "mousescroll", "run_secure", "setfflag", "getfflag", "loadstring", "decompile"
        ]
        
        targets.sort(key=len, reverse=True)

        for target in targets:
            # Lookbehind to ensure not a property, Group 1 for local check, Group 2 for word
            pattern = r'(?<!\.)(\blocal\s+)?\b(' + re.escape(target) + r')\b'
            
            def replace_match(match):
                prefix = match.group(1) # 'local ' or None
                word = match.group(2)   # The target global name
                if prefix:
                    return f"{prefix}{word}"
                return f"{self.var_Ma}[{self._mangle_string(word)}]"
            
            lua_code = re.sub(pattern, replace_match, lua_code)
            
        return lua_code

    # =========================================================================
    # OPAQUE PREDICATE & LOGIC INVERSION SYSTEM (Strategies A & B)
    # =========================================================================

    def _generate_junk_code(self):
        """
        Generates garbage Lua code that is syntactically valid but does nothing useful.
        Adheres to 'Lua vm fps... prefer wait(.001)' for loops.
        """
        var_name = self._generate_random_string(4)
        var_name_2 = self._generate_random_string(4)
        
        junk_types = [
            # Type 1: Useless Math Loop
            f"local {var_name} = 0; for i=1, {random.randint(2, 5)} do {var_name}={var_name}+1; wait(0.001); end",
            # Type 2: Table Junk
            f"local {var_name} = {{}}; {var_name}[1] = {random.randint(1,99)};",
            # Type 3: Simple math
            f"local {var_name} = {random.randint(10,999)} * {random.randint(2,9)};",
            # Type 4: Double variable junk
            f"local {var_name} = 1; local {var_name_2} = 2; {var_name} = {var_name} + {var_name_2};"
        ]
        return random.choice(junk_types)

    def _generate_opaque_predicate(self):
        """
        Generates a Contextual Opaque Predicate (Strategy B).
        Returns a tuple: (Condition String, Boolean Value)
        Example: ('(5 * 5 >= 0)', True)
        """
        
        # Strategy: Math Tautologies
        # We use raw numbers here; they will be mangled later by _mangle_number in the main pipeline.
        
        val_a = random.randint(10, 500)
        val_b = random.randint(10, 500)
        
        predicates = [
            # Square is always >= 0
            (f"( ({val_a} * {val_a}) >= 0 )", True),
            # Absolute value check
            (f"( math.abs({-val_a}) == {val_a} )", True),
            # Impossible check
            (f"( {val_a} < {-val_a} )", False),
            # Simple inequality
            (f"( {val_a} + {val_b} == {val_a + val_b} )", True)
        ]
        
        return random.choice(predicates)

    def _tokenize(self, code):
        """
        Splits code into a list of (type, value) tokens for safe AST traversal.
        Does NOT simplify logic.
        """
        token_specification = [
            ('COMMENT', r'--\[\[.*?\]\]|--[^\n]*'), # Matches --[[...]] or --...
            ('STRING',  r'("([^"\\]|\\.)*")|(\'([^\'\\]|\\.)*\')|(\[\[.*?\]\])'), # Strings
            ('KEYWORD', r'\b(if|then|else|elseif|end|do|function|repeat|until|while|for|local)\b'), # Keywords for blocking
            ('IDENT',   r'[A-Za-z_][A-Za-z0-9_]*'),    # Identifiers
            ('OP',      r'[+\-*/%^#=~<>()\[\]{},;.]'), # Operators
            ('NUMBER',  r'0[xX][0-9a-fA-F]+|\d+(\.\d*)?'), # Numbers (Updated to include Hex)
            ('WS',      r'\s+'),                       # Whitespace
            ('MISC',    r'.'),                         # Any other char
        ]
        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
        tokens = []
        for mo in re.finditer(tok_regex, code, re.DOTALL | re.MULTILINE):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'WS': continue 
            tokens.append((kind, value))
        return tokens

    def _reconstruct(self, tokens):
        """Rebuilds string from tokens (simple concatenation with spacing safety)."""
        # A simple join is often enough if we kept whitespace, but we stripped it.
        # We need to insert spaces between keywords/idents.
        out = []
        for i, (kind, val) in enumerate(tokens):
            if i > 0:
                prev_kind = tokens[i-1][0]
                # Add space if needed
                if (prev_kind in ['KEYWORD', 'IDENT', 'NUMBER'] and kind in ['KEYWORD', 'IDENT', 'NUMBER']):
                    out.append(' ')
            out.append(val)
        return "".join(out)

    def _process_logic_inversion(self, lua_code):
        """
        AST Traversal & Logic Inversion (Strategy A).
        Finds 'if A then B end' and converts to 'if not (A) then JUNK else B end'.
        This plays it safe: only inverts simple if-blocks with no else/elseif to avoid breaking logic.
        """
        tokens = self._tokenize(lua_code)
        
        # We will rebuild the code token by token.
        # When we hit an 'if', we try to scan ahead to see if it's a candidate for inversion.
        
        transformed_tokens = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            # Look for 'if'
            if token[0] == 'KEYWORD' and token[1] == 'if':
                
                # Check scanning ahead
                # We need to find 'then', capture condition, then find 'end' ensuring balanced nesting.
                # If we encounter 'else' or 'elseif' at the current depth, we ABORT inversion for this block.
                
                scan_i = i + 1
                condition_tokens = []
                
                # Scan Condition
                while scan_i < len(tokens) and tokens[scan_i][1] != 'then':
                    condition_tokens.append(tokens[scan_i])
                    scan_i += 1
                
                if scan_i < len(tokens) and tokens[scan_i][1] == 'then':
                    # Found 'then', consume it
                    scan_i += 1 
                    
                    # Scan Body
                    body_tokens = []
                    depth = 1 # We are inside the 'if'
                    
                    valid_candidate = True
                    
                    body_start_index = scan_i
                    
                    while scan_i < len(tokens):
                        t_kind, t_val = tokens[scan_i]
                        
                        if t_val == 'if' or t_val == 'do' or t_val == 'function' or t_val == 'repeat':
                            depth += 1
                        elif t_val == 'end' or t_val == 'until':
                            depth -= 1
                        elif (t_val == 'else' or t_val == 'elseif') and depth == 1:
                            # Found an else/elseif at the same level! Logic Inversion is unsafe/complex here.
                            valid_candidate = False
                            break
                        
                        if depth == 0:
                            # Found the closing 'end'
                            break
                            
                        body_tokens.append(tokens[scan_i])
                        scan_i += 1
                    
                    if valid_candidate and depth == 0:
                        # We successfully identified a simple if..then..end block.
                        # APPLY STRATEGY A: LOGIC INVERSION
                        # Structure: if not (CONDITION) then JUNK else BODY end
                        
                        junk_code_str = self._generate_junk_code()
                        # Tokenize junk code to add it to stream
                        junk_tokens = self._tokenize(junk_code_str)
                        
                        transformed_tokens.append(('KEYWORD', 'if'))
                        transformed_tokens.append(('KEYWORD', 'not'))
                        transformed_tokens.append(('OP', '('))
                        transformed_tokens.extend(condition_tokens)
                        transformed_tokens.append(('OP', ')'))
                        transformed_tokens.append(('KEYWORD', 'then'))
                        transformed_tokens.extend(junk_tokens)
                        transformed_tokens.append(('KEYWORD', 'else'))
                        transformed_tokens.extend(body_tokens)
                        transformed_tokens.append(('KEYWORD', 'end'))
                        
                        i = scan_i + 1 # Skip past the consumed tokens (including 'end')
                        continue

            # If not transformed, append original
            transformed_tokens.append(token)
            i += 1
            
        return self._reconstruct(transformed_tokens)

    def _inject_contextual_predicates(self, lua_code):
        """
        Strategy B: Wraps arbitrary valid statements in Opaque Predicates.
        if (TrueMath) then [Original] else [Junk] end
        """
        lines = lua_code.split('\n')
        out_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Safety check: Only wrap lines that look like complete statements (variable assignments, function calls)
            # Avoid wrapping 'end', 'else', or start of blocks if not careful.
            # Best to target variable assignments or void function calls.
            
            is_assignment = re.match(r'^(local\s+)?[a-zA-Z_0-9.]+\s*=[^=]', stripped)
            is_void_call = re.match(r'^[a-zA-Z_0-9.:]+\(.*\)$', stripped)
            
            if (is_assignment or is_void_call) and not stripped.endswith('do') and not stripped.endswith('then'):
                # 30% chance to wrap in opaque predicate
                if random.random() < 0.3:
                    pred_str, is_true = self._generate_opaque_predicate()
                    junk = self._generate_junk_code()
                    
                    if is_true:
                        # if (True) then Real else Junk
                        new_block = f"if {pred_str} then {line} else {junk} end"
                        out_lines.append(new_block)
                    else:
                        # if (False) then Junk else Real
                        new_block = f"if {pred_str} then {junk} else {line} end"
                        out_lines.append(new_block)
                else:
                    out_lines.append(line)
            else:
                out_lines.append(line)
                
        return "\n".join(out_lines)

    # =========================================================================
    # CONTROL FLOW FLATTENING (The "Maze")
    # =========================================================================

    def _apply_control_flow_flattening(self, lua_code):
        """
        Applies MoonVeil-Style Control Flow Flattening (CFF).
        
        1.  **Block Splitting**: Identifies 'if/then/end', 'while', 'repeat' structures to find safe "Basic Blocks" of code.
            To stay safe and avoid breaking scoping/upvalues, we primarily target the top-level statements or large function bodies.
            For this implementation, we will perform CFF on specific target functions if identified, or try to flatten the main chunk.
            
        2.  **State Machine**: Wraps blocks in a 'while state != 0 do' loop.
        
        3.  **Arithmetic Transitions**: Uses 'state = state + delta' instead of 'state = X'.
        """
        
        # NOTE: A full robust AST parser is needed for perfect CFF on complex nested structures.
        # We will implement a simplified version that targets sequential blocks of code 
        # to demonstrate the technique without breaking the complex nested logic of the input script.
        # We will wrap the MAIN execution flow into a flattened dispatcher.

        tokens = self._tokenize(lua_code)
        
        # We'll identify "chunks". A chunk is separated by logical boundaries.
        # For simplicity in this regex-based/token-based approach:
        # We will treat top-level chunks as our blocks.
        
        # However, to be safer with "local" scoping, we only flatten code that doesn't declare locals used across blocks.
        # OR we hoist declarations. Hoisting is complex.
        
        # ALTERNATIVE STRATEGY FOR STABILITY:
        # We will wrap the ENTIRE script in a dispatcher that only has 1 real block (the original code)
        # and several FAKE blocks (dead code) with Opaque Predicate jumps.
        # This creates the "Maze" structure without risking breaking local variables in the original code.
        # This effectively hides the entry point.
        
        # Let's build the "Maze" wrapper.
        
        real_block_id = random.randint(10000, 99999)
        exit_block_id = 0
        
        # Generate some fake blocks
        fake_blocks = []
        for _ in range(3):
            fake_id = random.randint(10000, 99999)
            while fake_id == real_block_id: fake_id = random.randint(10000, 99999)
            fake_content = self._generate_junk_code()
            fake_blocks.append((fake_id, fake_content))
            
        # The Dispatcher Variable
        var_state = self._generate_random_string(4)
        
        # Start State
        start_state = real_block_id
        
        # Construct the Dispatcher
        # while var_state ~= 0 do
        
        dispatcher_code = []
        dispatcher_code.append(f"local {var_state} = {start_state}")
        dispatcher_code.append(f"while {var_state} ~= 0 do")
        
        # Create a shuffled list of blocks (Real + Fake)
        all_blocks = []
        
        # 1. The Real Block
        # We wrap the original code in a block.
        # Important: If original code uses 'return', it might break the loop. 
        # But for a main chunk, it's usually fine.
        # To leave the loop, we set state = 0 at the end of the real block.
        
        # Arithmetic transition to 0: state = state + (0 - current)
        transition_to_end = f"{var_state} = {var_state} + ({exit_block_id} - {real_block_id})"
        
        real_block_content = f"{lua_code}\n{transition_to_end}"
        all_blocks.append((real_block_id, real_block_content))
        
        # 2. Add Fake Blocks
        for fid, fcontent in fake_blocks:
            # Fake blocks jump to another fake block or end to simulate flow
            target = 0
            # Arithmetic jump
            trans = f"{var_state} = {var_state} + ({target} - {fid})"
            all_blocks.append((fid, fcontent + "\n" + trans))
            
        # Shuffle them for the if/elseif ladder
        random.shuffle(all_blocks)
        
        # Build the if/elseif ladder
        for i, (bid, content) in enumerate(all_blocks):
            check_stmt = "if" if i == 0 else "elseif"
            
            # Opaque Predicate for the state check? 
            # state == bid
            # We can leave it simple for the switch, or obfuscate the constants later with _mangle_number.
            
            dispatcher_code.append(f"    {check_stmt} {var_state} == {bid} then")
            dispatcher_code.append(f"        {content}")
            
        dispatcher_code.append("    end")
        dispatcher_code.append("    wait(0.001)") # Safety wait for the loop
        dispatcher_code.append("end")
        
        return "\n".join(dispatcher_code)

    # =========================================================================
    # CORE PIPELINE
    # =========================================================================

    def _generate_header(self):
        """
        Generates the Wabi Sabi boilerplate.
        
        Loop Shifting Implementation:
        - Instead of iterating 1 to N, we iterate from Offset to N + (Offset-1)
        - Inside the loop, we use (kd-Zf+1) inline to get the real 1-based index
        - This is effective against simple deobfuscators that expect standard 1-to-N loops
        - The offset value (8960-8867) = 93 is used for obfuscation (matches OFFSET_VAL in _xor_encrypt)
        - Note: We inline the index calc to avoid per-iteration local variable allocation overhead
        """
        return f"""-- Generated by Wabi Sabi Obfuscator
local {self.var_Ma}=(getfenv())
local {self.var_string_char},{self.var_string_byte},{self.var_bit_xor}=(string.char),(string.byte),(bit32 and bit32.bxor or function(a,b) local p,c=1,0 while a>0 and b>0 do local ra,rb=a%2,b%2 if ra~=rb then c=c+p end a,b,p=(a-ra)/2,(b-rb)/2,p*2 end if a<b then a=b end while a>0 do local ra=a%2 if ra>0 then c=c+p end a,p=(a-ra)/2,p*2 end return c end)
local {self.var_Ea}=function(ib,da)
    local Vb=''
    local Zf=(8960-8867)
    for kd=Zf,#ib+(Zf-1) do
        local key_char = {self.var_string_byte}(da, ((kd-Zf+1)-2053812/22084)%#da + 1)
        local str_char = {self.var_string_byte}(ib, kd-Zf+1)
        Vb=Vb..{self.var_string_char}({self.var_bit_xor}(str_char, key_char))
    end
    return Vb
end
"""

    def _remove_comments(self, source):
        pattern = r'(?s)("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')|(\[(=*)\[.*?\]\3\])|(--\[(=*)\[.*?\]\5\]|--[^\n\r]*)'
        def replacer(match):
            if match.group(4): return " "
            return match.group(0)
        return re.sub(pattern, replacer, source)

    def obfuscate(self, lua_source):
        """
        Pipeline:
        1. Clean (Remove Comments)
        2. AST Logic Inversion (Strategy A)
        3. Contextual Predicates (Strategy B)
        4. Control Flow Flattening (The Maze)
        5. Logic Gate Booleans (MoonVeil) - Replaces true/false with logic expressions
        6. Mangle Numbers (including those generated in 2/3/4/5)
        7. Mangle Strings
        8. Virtualize Globals
        """
        
        # 1. Clean
        lua_source = self._remove_comments(lua_source)

        # 2. Strategy A: Logic Inversion (AST Traversal)
        lua_source = self._process_logic_inversion(lua_source)
        
        # 3. Strategy B: Contextual Predicates (Injection)
        lua_source = self._inject_contextual_predicates(lua_source)

        # 4. Control Flow Flattening (The Maze)
        # We wrap the processed code in the maze structure.
        lua_source = self._apply_control_flow_flattening(lua_source)

        # 5. Logic Gate Booleans (MoonVeil)
        # Replaces 'true' and 'false' literals with logic gate expressions
        # Must be done BEFORE number mangling so the numbers inside get obfuscated too
        lua_source = self._mangle_booleans(lua_source)

        # 6. Mangle Numbers
        # This will now also mangle the constants inside our Opaque Predicates and State Transitions
        # e.g., state = state + (-84379) -> state = state + ((10-94883) + ...)
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        def replace_number(match):
            return self._mangle_number(match.group(0))
        
        protected_code = re.sub(number_pattern, replace_number, lua_source)
        
        # 7. Mangle Strings
        string_pattern = r'("([^"]*)"|\'([^\']*)\')'
        def replace_string(match):
            if match.group(2) is not None:
                content = match.group(2)
            else:
                content = match.group(3)
            return self._mangle_string(content)

        protected_code = re.sub(string_pattern, replace_string, protected_code)

        # 8. Mangle Globals
        protected_code = self._mangle_globals(protected_code)

        # 9. Header
        final_code = self._generate_header() + "\n" + protected_code
        
        return final_code

# --- Usage ---
if __name__ == "__main__":
    input_code = """
    print("Initializing Matcha Script...")
    local LocalPlayer = game:GetService("Players").LocalPlayer
    
    local function check_enemy(target)
        if target then
            print("Enemy found")
            return true
        end
        return false
    end
    
    while true do
        print("Looping...")
        check_enemy(LocalPlayer)
        task.wait(1)
    end
    """
    
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
