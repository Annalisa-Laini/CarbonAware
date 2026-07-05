from data_processing import DataLoader, DataProcessor
from plotting import Plotter

def get_plot_type():
    """Prompts user for plot type and returns the input."""
    plot_type = input("Which type of plot do you want to generate? (seasonal/monthly): ").strip().lower()
    if plot_type not in ['seasonal', 'monthly']:
        print("Invalid input. Please enter 'seasonal' or 'monthly'.")
        return None
    return plot_type

def get_scale_choice():
    """Prompts user for scale choice and returns the input as a boolean."""
    scale_choice = input("Do you want to plot the scaled graph? (yes/no): ").strip().lower()
    if scale_choice not in ['yes', 'no']:
        print("Invalid input. Please enter 'yes' or 'no'.")
        return None
    return scale_choice == 'yes'  # Returns True for 'yes', False for 'no'

def load_and_process_data(file_path, scale):
    """Loads and processes the data based on file path and scaling requirement."""
    data_loader = DataLoader(file_path)
    data = data_loader.load_data()
    data_processor = DataProcessor(data, scale=scale)
    return data_processor.process_data()
    

def main():
    # Get user inputs
    plot_type = get_plot_type()
    if plot_type is None:
        return  # Exit if invalid plot type

    scale = get_scale_choice()
    if scale is None:
        return  # Exit if invalid scale choice

    # File path for CSVs (replace with actual path)
    file_path = r"energy_graphs\data\*.csv"

    processed_data = load_and_process_data(file_path, scale)
    
    # Load and process the data
    #EU_COUNTRIES = [
    #    'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czechia',
    #    'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary',
    #        'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
    #        'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia', 'Slovenia',
    #        'Spain', 'Sweden'
    #    ]
    EU_COUNTRIES = [
         'Poland', 'Portugal'    ]

    processed_data = processed_data[processed_data['country'].isin(EU_COUNTRIES)]

    # Create Plotter object with filtered data
    plotter = Plotter(processed_data, plot_type=plot_type, scale=scale)

    # Determine the appropriate plot function based on both plot type and scale
    plot_function_map = {
        ("seasonal", True): plotter.plot_seasonal_scaled,
        ("seasonal", False): plotter.plot_seasonal_not_scaled,
        ("monthly", True): plotter.plot_monthly_scaled,
        ("monthly", False): plotter.plot_monthly_not_scaled
    }

    # Call the corresponding plot function
    plot_function = plot_function_map.get((plot_type, scale))
    if plot_function:
        plot_function()
        print("image saved")
    else:
        print("Error: Plot function not found for the given combination of plot type and scale.")

if __name__ == "__main__":
    main()
