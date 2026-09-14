with open('lib/screens/login_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

# find where _LoginScreenState starts
insert_idx = content.find("class _LoginScreenState extends State<LoginScreen> {\n")
insert_idx = content.find("\n", insert_idx) + 1

init_state = """  @override
  void initState() {
    super.initState();
    _checkAutoLogin();
  }

  Future<void> _checkAutoLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token != null && token.isNotEmpty) {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const HubScreen()),
      );
    }
  }

"""

if "_checkAutoLogin" not in content:
    content = content[:insert_idx] + init_state + content[insert_idx:]

with open('lib/screens/login_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated login_screen.dart for auto-login")
