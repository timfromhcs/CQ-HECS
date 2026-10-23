#pragma once
// Shared constant-angle expression evaluator for the CQ-HECS QASM parsers.
//
// Supports exactly: decimal/scientific literals, ``pi``, unary ``+``/``-``,
// parentheses and binary ``+ - * /``. It never falls back to a default value:
// ``evaluate()`` returns false for malformed input, division by zero and
// non-finite results. Both the CLI parser and the C-ABI parser use this code so
// the accepted grammar cannot drift between them.

#include <cctype>
#include <cmath>
#include <string>

namespace cq_hecs {

class AngleExpression {
public:
    explicit AngleExpression(const std::string& text) : text_(text) {}

    bool evaluate(double& out) {
        pos_ = 0;
        if (!parse_sum(out)) return false;
        skip_ws();
        if (pos_ != text_.size()) return false;
        return std::isfinite(out);
    }

private:
    void skip_ws() {
        while (pos_ < text_.size() &&
               std::isspace(static_cast<unsigned char>(text_[pos_]))) {
            ++pos_;
        }
    }

    bool parse_sum(double& out) {
        double value = 0.0;
        if (!parse_product(value)) return false;
        for (;;) {
            skip_ws();
            if (pos_ >= text_.size() || (text_[pos_] != '+' && text_[pos_] != '-')) break;
            const char op = text_[pos_++];
            double rhs = 0.0;
            if (!parse_product(rhs)) return false;
            value = (op == '+') ? value + rhs : value - rhs;
            if (!std::isfinite(value)) return false;
        }
        out = value;
        return true;
    }

    bool parse_product(double& out) {
        double value = 0.0;
        if (!parse_factor(value)) return false;
        for (;;) {
            skip_ws();
            if (pos_ >= text_.size() || (text_[pos_] != '*' && text_[pos_] != '/')) break;
            const char op = text_[pos_++];
            double rhs = 0.0;
            if (!parse_factor(rhs)) return false;
            if (op == '*') {
                value *= rhs;
            } else {
                if (rhs == 0.0) return false;
                value /= rhs;
            }
            if (!std::isfinite(value)) return false;
        }
        out = value;
        return true;
    }

    bool parse_factor(double& out) {
        skip_ws();
        if (pos_ >= text_.size()) return false;

        if (text_[pos_] == '+' || text_[pos_] == '-') {
            const char op = text_[pos_++];
            double value = 0.0;
            if (!parse_factor(value)) return false;
            out = (op == '-') ? -value : value;
            return std::isfinite(out);
        }

        if (text_[pos_] == '(') {
            ++pos_;
            double value = 0.0;
            if (!parse_sum(value)) return false;
            skip_ws();
            if (pos_ >= text_.size() || text_[pos_] != ')') return false;
            ++pos_;
            out = value;
            return true;
        }

        if (text_.compare(pos_, 2, "pi") == 0) {
            pos_ += 2;
            out = 3.14159265358979323846;
            return true;
        }

        const size_t start = pos_;
        bool has_digit = false;
        while (pos_ < text_.size() &&
               (std::isdigit(static_cast<unsigned char>(text_[pos_])) || text_[pos_] == '.')) {
            if (text_[pos_] != '.') has_digit = true;
            ++pos_;
        }
        if (!has_digit) return false;

        if (pos_ < text_.size() && (text_[pos_] == 'e' || text_[pos_] == 'E')) {
            const size_t exp_start = pos_;
            ++pos_;
            if (pos_ < text_.size() && (text_[pos_] == '+' || text_[pos_] == '-')) ++pos_;
            bool exp_digit = false;
            while (pos_ < text_.size() &&
                   std::isdigit(static_cast<unsigned char>(text_[pos_]))) {
                exp_digit = true;
                ++pos_;
            }
            if (!exp_digit) pos_ = exp_start;
        }

        try {
            const std::string literal = text_.substr(start, pos_ - start);
            size_t consumed = 0;
            const double value = std::stod(literal, &consumed);
            // std::stod accepts a prefix ("3.14.15" -> 3.14), so require the
            // whole literal to be consumed.
            if (consumed != literal.size()) return false;
            if (!std::isfinite(value)) return false;
            out = value;
        } catch (...) {
            return false;
        }
        return true;
    }

    const std::string& text_;
    size_t pos_ = 0;
};

}  // namespace cq_hecs
