import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/login_screen.dart';
import 'brand.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  GoogleFonts.config.allowRuntimeFetching = true;

  runApp(
    MaterialApp(
      title: 'Bonso | SKALE IA',
      theme: ThemeData.dark().copyWith(
        colorScheme: const ColorScheme.dark(
          primary: BonsoBrand.lime,
          secondary: BonsoBrand.aqua,
          surface: BonsoBrand.surface,
          background: BonsoBrand.ink,
        ),
        textTheme: GoogleFonts.interTextTheme(
          ThemeData.dark().textTheme,
        ).apply(
          fontFamilyFallback: const ['Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: BonsoBrand.surface,
          elevation: 0,
          centerTitle: true,
        ),
        scaffoldBackgroundColor: BonsoBrand.ink,
      ),
      home: const LoginScreen(),
      debugShowCheckedModeBanner: false,
    ),
  );
}
