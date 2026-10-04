import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/landing_screen.dart';
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
      builder: (context, child) {
        // Evita que el autoescalado del navegador móvil deforme el layout tras
        // volver a la app. El rango conserva la accesibilidad del texto.
        final media = MediaQuery.of(context);
        return MediaQuery(
          data: media.copyWith(
            // Mantiene compatibilidad con las versiones de Flutter usadas por
            // los clientes ya instalados; la API moderna se migra al actualizar.
            textScaleFactor: media.textScaleFactor.clamp(0.9, 1.25).toDouble(),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
      home: const LandingScreen(),
      debugShowCheckedModeBanner: false,
    ),
  );
}
